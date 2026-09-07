"""HTML visibility evidence shared by content coverage and residue checks.

This is a bounded static analysis of authored HTML/CSS, not a browser layout
engine. Coverage fails closed on ambiguous visibility; residue checks retain
potentially visible copy so unsupported styling cannot hide raw markup.
"""
from __future__ import annotations

import re
from html import unescape
from html.parser import HTMLParser


def _decode_css_escapes(text: str) -> str:
    """Decode the CSS escapes needed to recognize property names and values."""
    def replace_hex(match: re.Match) -> str:
        try:
            return chr(int(match.group(1), 16))
        except (ValueError, OverflowError):
            return ""

    text = re.sub(r"\\([0-9a-fA-F]{1,6})\s?", replace_hex, text)
    return re.sub(r"\\([^\r\n])", r"\1", text)


def _css_numeric_value(value: str) -> tuple[float, str] | None:
    """Parse a small, deterministic subset of CSS numeric expressions."""
    value = re.sub(r"\s+", "", value.lower())
    direct = re.fullmatch(r"([-+]?(?:\d+(?:\.\d*)?|\.\d+))(%|[a-z]+)?", value)
    if direct:
        return float(direct.group(1)), direct.group(2) or ""
    function = re.fullmatch(r"(calc|min|max|clamp)\((.*)\)", value)
    if not function:
        return None
    name, body = function.groups()
    if name == "calc":
        return _css_numeric_value(body)
    parts = [_css_numeric_value(part) for part in body.split(",")]
    if not parts or any(part is None for part in parts):
        return None
    parsed = [part for part in parts if part is not None]
    units = {unit for number, unit in parsed if number != 0 and unit}
    if len(units) > 1:
        return None
    unit = next(iter(units), next((u for _, u in parsed if u), ""))
    values = [number for number, _ in parsed]
    if name == "min":
        return min(values), unit
    if name == "max":
        return max(values), unit
    if len(values) == 3:
        lower, preferred, upper = values
        return max(lower, min(preferred, upper)), unit
    return None


def _is_zero_css_value(value: str) -> bool:
    parsed = _css_numeric_value(value)
    return parsed is not None and parsed[0] == 0


def _is_extreme_css_offset(value: str) -> bool:
    parsed = _css_numeric_value(value)
    if parsed is None:
        return False
    number, unit = parsed
    threshold = 100 if unit in {"%", "em", "rem"} else 2000
    return abs(number) >= threshold


class _DocumentStyleCollector(HTMLParser):
    """Collect stylesheet bodies and decoded inline style attributes."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.style_blocks: list[str] = []
        self.inline_styles: list[str] = []
        self._style_parts: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "style":
            self._style_parts = []
        self.inline_styles.extend(
            value
            for name, value in attrs
            if name.lower() == "style" and value is not None
        )

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "style" and self._style_parts is not None:
            self.style_blocks.append("".join(self._style_parts))
            self._style_parts = None

    def handle_data(self, data: str) -> None:
        if self._style_parts is not None:
            self._style_parts.append(data)

    def close(self) -> None:
        super().close()
        if self._style_parts is not None:
            self.style_blocks.append("".join(self._style_parts))
            self._style_parts = None


def _custom_property_names(css: str) -> list[str]:
    """Return custom-property declarations while ignoring quoted text.

    This intentionally over-collects declarations from selectors and at-rules:
    any declaration outside an unconditional root rule makes cross-rule
    resolution unsafe. False positives therefore disable an optimization
    instead of admitting hidden evidence.
    """
    names: list[str] = []
    quote = ""
    escaped = False
    index = 0
    while index < len(css):
        char = css[index]
        if escaped:
            escaped = False
            index += 1
            continue
        if char == "\\":
            escaped = True
            index += 1
            continue
        if quote:
            if char == quote:
                quote = ""
            index += 1
            continue
        if char in {'"', "'"}:
            quote = char
            index += 1
            continue
        if css.startswith("--", index):
            match = re.match(r"--[\w-]+", css[index:])
            if match:
                name = match.group(0)
                end = index + len(name)
                cursor = end
                while cursor < len(css) and css[cursor].isspace():
                    cursor += 1
                if cursor < len(css) and css[cursor] == ":":
                    names.append(name)
                index = end
                continue
        index += 1
    return names


def _top_level_css_rules(css: str) -> list[tuple[str, str]] | None:
    """Split a stylesheet into balanced top-level ``(prelude, body)`` rules."""
    rules: list[tuple[str, str]] = []
    start = 0
    index = 0
    quote = ""
    escaped = False
    paren_depth = 0
    bracket_depth = 0
    while index < len(css):
        char = css[index]
        if escaped:
            escaped = False
            index += 1
            continue
        if char == "\\":
            escaped = True
            index += 1
            continue
        if quote:
            if char == quote:
                quote = ""
            index += 1
            continue
        if char in {'"', "'"}:
            quote = char
            index += 1
            continue
        if char == "(":
            paren_depth += 1
        elif char == ")":
            if paren_depth == 0:
                return None
            paren_depth -= 1
        elif char == "[":
            bracket_depth += 1
        elif char == "]":
            if bracket_depth == 0:
                return None
            bracket_depth -= 1
        elif char == ";" and paren_depth == 0 and bracket_depth == 0:
            start = index + 1
        elif char == "{" and paren_depth == 0 and bracket_depth == 0:
            prelude = css[start:index].strip()
            body_start = index + 1
            depth = 1
            inner_quote = ""
            inner_escaped = False
            index += 1
            while index < len(css) and depth:
                inner = css[index]
                if inner_escaped:
                    inner_escaped = False
                elif inner == "\\":
                    inner_escaped = True
                elif inner_quote:
                    if inner == inner_quote:
                        inner_quote = ""
                elif inner in {'"', "'"}:
                    inner_quote = inner
                elif inner == "{":
                    depth += 1
                elif inner == "}":
                    depth -= 1
                index += 1
            if depth or inner_quote:
                return None
            rules.append((prelude, css[body_start:index - 1]))
            start = index
            paren_depth = 0
            bracket_depth = 0
            continue
        elif char == "}" and paren_depth == 0 and bracket_depth == 0:
            return None
        index += 1
    if quote or escaped or paren_depth or bracket_depth:
        return None
    return rules


def _css_declarations(body: str) -> list[tuple[str, str]] | None:
    """Parse a declaration block without splitting quoted or functional values."""
    if "{" in body or "}" in body:
        return None
    parts: list[str] = []
    start = 0
    quote = ""
    escaped = False
    paren_depth = 0
    bracket_depth = 0
    for index, char in enumerate(body):
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if quote:
            if char == quote:
                quote = ""
            continue
        if char in {'"', "'"}:
            quote = char
        elif char == "(":
            paren_depth += 1
        elif char == ")":
            if paren_depth == 0:
                return None
            paren_depth -= 1
        elif char == "[":
            bracket_depth += 1
        elif char == "]":
            if bracket_depth == 0:
                return None
            bracket_depth -= 1
        elif char == ";" and paren_depth == 0 and bracket_depth == 0:
            parts.append(body[start:index])
            start = index + 1
    if quote or escaped or paren_depth or bracket_depth:
        return None
    parts.append(body[start:])

    declarations: list[tuple[str, str]] = []
    for part in parts:
        name, separator, value = part.partition(":")
        if not separator:
            continue
        declarations.append((re.sub(r"\s+", "", name), value.strip()))
    return declarations


def _document_custom_properties(raw: str) -> dict[str, str]:
    """Return unconditional root properties safe to resolve across rules.

    The checker has no CSS cascade. A property is reusable only when every
    declaration is on an unconditional ``:root`` or ``html`` rule and every
    value is identical. Scoped, conditional, inline, registered, or malformed
    declarations disable that property instead of weakening fail-closed checks.
    """
    collector = _DocumentStyleCollector()
    collector.feed(raw)
    collector.close()

    all_names: list[str] = []
    root_values: dict[str, list[str]] = {}
    for block in collector.style_blocks:
        clean = re.sub(r"/\*.*?\*/", "", block, flags=re.S)
        clean = _decode_css_escapes(clean)
        if re.search(r"@property\b", clean, flags=re.I):
            return {}
        all_names.extend(_custom_property_names(clean))
        rules = _top_level_css_rules(clean)
        if rules is None:
            return {}
        for selectors, body in rules:
            roots = [selector.strip().lower() for selector in selectors.split(",")]
            if not roots or any(selector not in {":root", "html"} for selector in roots):
                continue
            declarations = _css_declarations(body)
            if declarations is None:
                return {}
            for name, value in declarations:
                if not name.startswith("--"):
                    continue
                value = re.sub(r"!\s*important\s*$", "", value, flags=re.I).strip()
                root_values.setdefault(name, []).append(value)
    for inline in collector.inline_styles:
        clean = re.sub(r"/\*.*?\*/", "", inline, flags=re.S)
        all_names.extend(_custom_property_names(_decode_css_escapes(clean)))

    counts: dict[str, int] = {}
    for name in all_names:
        counts[name] = counts.get(name, 0) + 1
    return {
        name: values[0]
        for name, values in root_values.items()
        if counts.get(name) == len(values) and len(set(values)) == 1
    }


def _style_state(
    style: str,
    *,
    fail_closed: bool,
    replaced_element: bool = False,
    custom_properties: dict[str, str] | None = None,
) -> tuple[bool, bool]:
    """Return ``(hidden, ambiguous)`` for a declaration block.

    CSS comments are removed first because browsers accept declarations such
    as ``display/**/: none``. The coverage gate must not treat those elements
    as visible merely because the declaration was split by a comment.
    """
    clean = re.sub(r"/\*.*?\*/", "", style, flags=re.S)
    clean = _decode_css_escapes(clean)
    declarations = _css_declarations(clean)
    if declarations is None:
        return False, fail_closed
    properties: dict[str, tuple[str, bool]] = {
        name: (value, False) for name, value in (custom_properties or {}).items()
    }
    for name, value in declarations:
        name = re.sub(r"\s+", "", name)
        if not name.startswith("--"):
            name = name.lower()
        important = re.search(r"!\s*important\s*$", value, flags=re.I) is not None
        value = re.sub(r"!\s*important\s*$", "", value, flags=re.I)
        value = re.sub(r"\s+", "", value)
        previous = properties.get(name)
        if previous is None or important or not previous[1]:
            properties[name] = (value, important)

    def resolved(name: str, depth: int = 0) -> tuple[str, bool]:
        if name not in properties:
            return "", False
        if depth > 8:
            return "", True
        value = properties[name][0]
        match = re.fullmatch(r"(?i:var)\((--[\w-]+)(?:,(.*))?\)", value)
        if not match:
            return value, False
        custom_name, fallback = match.groups()
        if custom_name in properties:
            return resolved(custom_name, depth + 1)
        if fallback is None:
            return "", True
        temporary_name = f"--kami-fallback-{depth}"
        properties[temporary_name] = (fallback, False)
        try:
            return resolved(temporary_name, depth + 1)
        finally:
            properties.pop(temporary_name, None)

    def resolved_css(name: str) -> tuple[str, bool]:
        value, ambiguous = resolved(name)
        return value.lower(), ambiguous

    display, display_ambiguous = resolved_css("display")
    visibility, visibility_ambiguous = resolved_css("visibility")
    if fail_closed and (
        (display_ambiguous and "display" in properties)
        or (visibility_ambiguous and "visibility" in properties)
    ):
        return False, True
    if display == "none" or display.startswith("var("):
        return True, False
    if visibility in {"hidden", "collapse"} or visibility.startswith("var("):
        return True, False
    opacity, opacity_ambiguous = resolved_css("opacity")
    if opacity_ambiguous and "opacity" in properties and fail_closed:
        return False, True
    if _is_zero_css_value(opacity):
        return True, False
    font_size, font_size_ambiguous = resolved_css("font-size")
    if font_size_ambiguous and "font-size" in properties and fail_closed:
        return False, True
    if _is_zero_css_value(font_size):
        return True, False
    color, color_ambiguous = resolved_css("color")
    if color_ambiguous and "color" in properties and fail_closed:
        return False, True
    if color == "transparent":
        return True, False
    transform, transform_ambiguous = resolved_css("transform")
    if transform_ambiguous and "transform" in properties and fail_closed:
        return False, True
    if (
        re.search(r"scale(?:x|y)?\([-+]?(?:0+(?:\.0*)?|\.0+)\)", transform)
        or re.search(
            r"scale\([-+]?(?:0+(?:\.0*)?|\.0+),"
            r"[-+]?(?:0+(?:\.0*)?|\.0+)\)",
            transform,
        )
    ):
        return True, False
    matrix = re.search(r"matrix\(([^)]*)\)", transform)
    if matrix:
        try:
            values = [float(value) for value in matrix.group(1).split(",")]
        except ValueError:
            values = []
        if len(values) == 6 and all(value == 0 for value in values[:4]):
            return True, False
    if re.search(r"translate(?:x|y)?\([^)]*(?:-[2-9]\d{3,}|-[1-9]\d{4,})", transform):
        return True, False
    if fail_closed and "transform" in properties and "var(" in transform:
        return False, True
    for property_name in ("scale", "zoom"):
        value, ambiguous = resolved_css(property_name)
        if ambiguous and property_name in properties and fail_closed:
            return False, True
        if _is_zero_css_value(value):
            return True, False
    content_visibility, content_visibility_ambiguous = resolved_css("content-visibility")
    if content_visibility_ambiguous and "content-visibility" in properties and fail_closed:
        return False, True
    if content_visibility == "hidden":
        return True, False
    filter_value, filter_ambiguous = resolved_css("filter")
    if filter_ambiguous and "filter" in properties and fail_closed:
        return False, True
    if re.search(r"opacity\((?:0+(?:\.0*)?|\.0+)(?:%)?\)", filter_value):
        return True, False
    if fail_closed and "filter" in properties and "url(" in filter_value:
        return False, True
    if fail_closed:
        for property_name in ("mask", "mask-image", "-webkit-mask", "-webkit-mask-image"):
            value, ambiguous = resolved_css(property_name)
            if property_name in properties and (ambiguous or value not in {"", "none"}):
                return False, True
    if fail_closed:
        for property_name in (
            "top", "right", "bottom", "left", "inset", "inset-inline",
            "inset-block", "margin-top", "margin-right", "margin-bottom",
            "margin-left",
        ):
            value, ambiguous = resolved_css(property_name)
            if property_name not in properties:
                continue
            if ambiguous:
                return False, True
            if _is_extreme_css_offset(value):
                return True, False
    text_indent, text_indent_ambiguous = resolved_css("text-indent")
    if text_indent_ambiguous and "text-indent" in properties and fail_closed:
        return False, True
    if _is_extreme_css_offset(text_indent):
        return True, False
    clip, clip_ambiguous = resolved_css("clip")
    clip_path, clip_path_ambiguous = resolved_css("clip-path")
    if fail_closed and (
        (clip_ambiguous and "clip" in properties)
        or (clip_path_ambiguous and "clip-path" in properties)
    ):
        return False, True
    if clip in {"rect(0,0,0,0)", "rect(0px,0px,0px,0px)"}:
        return True, False
    if clip_path in {"inset(50%)", "inset(100%)", "circle(0)", "circle(0px)"}:
        return True, False
    if fail_closed and "clip" in properties and clip not in {"", "auto"}:
        return False, True
    if fail_closed and "clip-path" in properties and clip_path not in {"", "none"}:
        return False, True
    width, width_ambiguous = resolved_css("width")
    max_width, max_width_ambiguous = resolved_css("max-width")
    height, height_ambiguous = resolved_css("height")
    max_height, max_height_ambiguous = resolved_css("max-height")
    overflow, overflow_ambiguous = resolved_css("overflow")
    if fail_closed and (
        (width_ambiguous and "width" in properties)
        or (max_width_ambiguous and "max-width" in properties)
        or (height_ambiguous and "height" in properties)
        or (max_height_ambiguous and "max-height" in properties)
    ):
        return False, True
    if overflow_ambiguous and "overflow" in properties and fail_closed:
        return False, True
    zero_width = _is_zero_css_value(width) or _is_zero_css_value(max_width)
    zero_height = _is_zero_css_value(height) or _is_zero_css_value(max_height)
    if (zero_width or zero_height) and (
        replaced_element or overflow in {"hidden", "clip"}
    ):
        return True, False
    if fail_closed:
        for property_name, value, ambiguous in (
            ("opacity", opacity, opacity_ambiguous),
            ("font-size", font_size, font_size_ambiguous),
            ("width", width, width_ambiguous),
            ("max-width", max_width, max_width_ambiguous),
            ("height", height, height_ambiguous),
            ("max-height", max_height, max_height_ambiguous),
        ):
            if property_name in properties and (
                ambiguous or ("(" in value and _css_numeric_value(value) is None)
            ):
                return False, True
    return False, False


def _style_hides(
    style: str,
    *,
    fail_closed: bool,
    replaced_element: bool = False,
    custom_properties: dict[str, str] | None = None,
) -> bool:
    return _style_state(
        style,
        custom_properties=custom_properties,
        fail_closed=fail_closed,
        replaced_element=replaced_element,
    )[0]


def _css_hidden_filters(
    raw: str,
    *,
    fail_closed: bool,
    custom_properties: dict[str, str] | None = None,
) -> tuple[
    set[str], set[str], set[str], set[tuple[str, str | None]],
    set[str], set[str], set[str], set[tuple[str, str | None]], bool,
]:
    """Return conservative class, id, and tag filters for hidden CSS rules.

    The stdlib parser does not implement the CSS cascade. For compound
    selectors, it marks the target class/id when available; for a bare target
    such as ``.concealed img``, it marks the nearest ancestor class/id. This
    can reject an ambiguous document, but it cannot turn hidden evidence into
    a coverage pass. Pseudo-elements are ignored because they do not hide the
    underlying element.
    """
    hidden_classes: set[str] = set()
    hidden_ids: set[str] = set()
    hidden_tags: set[str] = set()
    hidden_attrs: set[tuple[str, str | None]] = set()
    ambiguous_classes: set[str] = set()
    ambiguous_ids: set[str] = set()
    ambiguous_tags: set[str] = set()
    ambiguous_attrs: set[tuple[str, str | None]] = set()
    globally_ambiguous = False
    decoded_markup = unescape(raw)
    if fail_closed and re.search(
        r"<link\b[^>]*\bstylesheet\b[^>]*>",
        decoded_markup,
        flags=re.I,
    ):
        ambiguous_tags.add("*")
        globally_ambiguous = True
    style_blocks = re.findall(r"<style\b[^>]*>(.*?)</style\s*>", raw, flags=re.I | re.S)
    for block in style_blocks:
        clean = re.sub(r"/\*.*?\*/", "", block, flags=re.S)
        clean = _decode_css_escapes(clean)
        if fail_closed and re.search(r"@import\b", clean, flags=re.I):
            ambiguous_tags.add("*")
            globally_ambiguous = True
        for selectors, body in re.findall(r"([^{}]+)\{([^{}]*)\}", clean, flags=re.S):
            hides, body_ambiguous = _style_state(
                body,
                fail_closed=fail_closed,
                custom_properties=custom_properties,
            )
            if not hides and not body_ambiguous:
                continue
            class_store = ambiguous_classes if body_ambiguous else hidden_classes
            id_store = ambiguous_ids if body_ambiguous else hidden_ids
            tag_store = ambiguous_tags if body_ambiguous else hidden_tags
            attr_store = ambiguous_attrs if body_ambiguous else hidden_attrs
            selectors = _decode_css_escapes(selectors)
            if (
                re.search(r":[\w-]+\s*\(", selectors)
                or re.search(r"[+~]", selectors)
                or re.search(r"\[[^\]]*(?:[~|^$*]=)", selectors)
                or re.search(r"\[[^\]]*,[^\]]*\]", selectors)
            ):
                if fail_closed:
                    ambiguous_tags.add("*")
                    globally_ambiguous = True
                continue
            for selector in selectors.split(","):
                selector = selector.strip()
                if not selector or "::" in selector:
                    continue
                compounds = [
                    part for part in re.split(r"\s+|[>+~]", selector) if part
                ]
                if not compounds:
                    continue
                target = compounds[-1]
                target_classes = set(re.findall(r"\.([\w-]+)", target))
                target_ids = set(re.findall(r"#([\w-]+)", target))
                target_attrs = {
                    (
                        match.group(1).lower(),
                        next(
                            (value for value in match.groups()[1:] if value is not None),
                            None,
                        ),
                    )
                    for match in re.finditer(
                        r"\[\s*([\w-]+)(?:\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|([^\]\s]+)))?\s*\]",
                        target,
                    )
                }
                if ":not(" not in target and (target_classes or target_ids):
                    class_store.update(target_classes)
                    id_store.update(target_ids)
                    continue
                if target_attrs:
                    attr_store.update(target_attrs)
                    continue
                if target.startswith(":root"):
                    tag_store.add("html")
                    continue
                ancestors = " ".join(compounds[:-1])
                ancestor_classes = set(re.findall(r"\.([\w-]+)", ancestors))
                ancestor_ids = set(re.findall(r"#([\w-]+)", ancestors))
                if ancestor_classes or ancestor_ids:
                    class_store.update(ancestor_classes)
                    id_store.update(ancestor_ids)
                    continue
                tag_match = re.match(r"(?:\*|[a-zA-Z][\w-]*)", target)
                if tag_match:
                    tag_store.add(tag_match.group(0).lower())
                else:
                    ambiguous_tags.add("*")
                    globally_ambiguous = True
    return (
        hidden_classes,
        hidden_ids,
        hidden_tags,
        hidden_attrs,
        ambiguous_classes,
        ambiguous_ids,
        ambiguous_tags,
        ambiguous_attrs,
        globally_ambiguous,
    )


def css_hidden_selectors(raw: str) -> tuple[set[str], set[str]]:
    """Return class and id filters hidden by inline stylesheet rules."""
    hidden_classes, hidden_ids, _, _, _, _, _, _, _ = _css_hidden_filters(
        raw,
        fail_closed=False,
    )
    return hidden_classes, hidden_ids


class _HtmlVisibilityParser(HTMLParser):
    """Shared fail-closed visibility state for text and resource parsers."""

    _VOID_TAGS = {
        "area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr",
    }
    _P_IMPLICIT_CLOSE_STARTS = {
        "address", "article", "aside", "blockquote", "details", "div",
        "dl", "fieldset", "figcaption", "figure", "footer", "form",
        "h1", "h2", "h3", "h4", "h5", "h6", "header", "hgroup", "hr",
        "main", "menu", "nav", "ol", "p", "pre", "section", "table", "ul",
    }
    _OPTIONAL_REPEAT_TAGS = {
        "dd", "dt", "li", "option", "tbody", "td", "tfoot", "th", "thead", "tr",
    }
    _REPLACED_TAGS = {"audio", "embed", "iframe", "image", "img", "object", "svg", "video"}
    _PRESENTATION_STYLE_ATTRS = {
        "clip", "clip-path", "color", "display", "filter", "font-size", "height",
        "mask", "mask-image", "max-height", "max-width", "opacity", "overflow",
        "transform", "visibility", "width",
    }
    _SVG_POSITIONED_TAGS = {
        "circle", "ellipse", "foreignobject", "image", "rect", "svg", "text", "tspan", "use",
    }

    def __init__(
        self,
        hidden_classes: set[str],
        hidden_ids: set[str],
        hidden_tags: set[str],
        hidden_attrs: set[tuple[str, str | None]],
        ambiguous_classes: set[str],
        ambiguous_ids: set[str],
        ambiguous_tags: set[str],
        ambiguous_attrs: set[tuple[str, str | None]],
        visibility_ambiguous: bool,
        *,
        skip_tags: set[str],
        fail_closed: bool,
        residue_mode: bool = False,
        custom_properties: dict[str, str] | None = None,
    ) -> None:
        super().__init__(convert_charrefs=True)
        self._custom_properties = custom_properties
        self._hidden_classes = hidden_classes
        self._hidden_ids = hidden_ids
        self._hidden_tags = hidden_tags
        self._hidden_attrs = hidden_attrs
        self._ambiguous_classes = ambiguous_classes
        self._ambiguous_ids = ambiguous_ids
        self._ambiguous_tags = ambiguous_tags
        self._ambiguous_attrs = ambiguous_attrs
        self._skip_tags = skip_tags
        self._fail_closed = fail_closed
        self._residue_mode = residue_mode
        self._visibility_ambiguous = visibility_ambiguous
        self._skip_depth = 0
        self._ambiguous_depth = 0
        self._skip_stack: list[tuple[str, bool, bool]] = []
        self._svg_viewports: list[tuple[float, float, float, float]] = []
        self._ambiguous_markup = False

    def _mark_ambiguous(self) -> None:
        self._ambiguous_markup = True
        self._skip_stack.clear()
        self._svg_viewports.clear()
        self._skip_depth = 1 if self._fail_closed else 0
        self._ambiguous_depth = 1 if self._fail_closed else 0

    def _pop_top(self) -> None:
        tag, hidden, ambiguous = self._skip_stack.pop()
        if tag == "svg" and self._svg_viewports:
            self._svg_viewports.pop()
        if hidden:
            self._skip_depth = max(0, self._skip_depth - 1)
        if ambiguous:
            self._ambiguous_depth = max(0, self._ambiguous_depth - 1)

    @staticmethod
    def _svg_viewport(attrs_map: dict[str, str]) -> tuple[float, float, float, float] | None:
        raw = attrs_map.get("viewbox", "")
        if raw:
            try:
                values = [float(value) for value in re.split(r"[\s,]+", raw.strip())]
            except ValueError:
                values = []
            if len(values) == 4 and values[2] > 0 and values[3] > 0:
                return values[0], values[1], values[2], values[3]
        width = _css_numeric_value(attrs_map.get("width", ""))
        height = _css_numeric_value(attrs_map.get("height", ""))
        if width and height and width[0] > 0 and height[0] > 0:
            return 0.0, 0.0, width[0], height[0]
        return None

    def _svg_position_state(
        self,
        tag: str,
        attrs_map: dict[str, str],
    ) -> tuple[bool, bool]:
        if tag not in self._SVG_POSITIONED_TAGS:
            return False, False
        viewport = self._svg_viewports[-1] if self._svg_viewports else None
        if viewport is not None and tag in {"foreignobject", "text", "tspan"}:
            # A coordinate point does not prove that the complete glyph or
            # foreign-object box intersects the viewport. Renderer box data is
            # required, so SVG text cannot be deterministic atomic evidence.
            return False, True
        parsed_positions: dict[str, float] = {}
        for name in ("x", "y", "dx", "dy"):
            if name not in attrs_map:
                continue
            parsed = _css_numeric_value(attrs_map[name])
            if parsed is None or parsed[1] not in {"", "px", "pt"}:
                return False, True
            parsed_positions[name] = parsed[0]
        if tag == "svg" and viewport is not None and parsed_positions:
            # Nested SVG establishes another viewport. Proving its transformed
            # overlap requires the renderer, so do not accept facts from it as
            # deterministic static evidence.
            return False, True
        if any(parsed_positions.get(name, 0) != 0 for name in ("dx", "dy")):
            return False, True
        if viewport is None:
            if any(abs(value) >= 10000 for value in parsed_positions.values()):
                return True, False
            return False, False
        min_x, min_y, view_width, view_height = viewport
        x = parsed_positions.get("x", min_x)
        y = parsed_positions.get("y", min_y)
        max_x = min_x + view_width
        max_y = min_y + view_height
        if tag == "image":
            image_width = _css_numeric_value(attrs_map.get("width", ""))
            image_height = _css_numeric_value(attrs_map.get("height", ""))
            if (
                image_width is None
                or image_height is None
                or image_width[1] not in {"", "px", "pt"}
                or image_height[1] not in {"", "px", "pt"}
                or image_width[0] <= 0
                or image_height[0] <= 0
            ):
                return False, True
            right = x + image_width[0]
            bottom = y + image_height[0]
            if right <= min_x or x >= max_x or bottom <= min_y or y >= max_y:
                return True, False
            if x < min_x or right > max_x or y < min_y or bottom > max_y:
                return False, True
        elif x < min_x or x > max_x or y < min_y or y > max_y:
            return False, True
        return False, False

    @staticmethod
    def _implicitly_closed_by_start(open_tag: str, new_tag: str) -> bool:
        if open_tag == "p" and new_tag in _HtmlVisibilityParser._P_IMPLICIT_CLOSE_STARTS:
            return True
        if open_tag == "li" and new_tag == "li":
            return True
        if open_tag in {"dd", "dt"} and new_tag in {"dd", "dt"}:
            return True
        if open_tag in {"rp", "rt"} and new_tag in {"rp", "rt"}:
            return True
        if open_tag == "option" and new_tag in {"option", "optgroup"}:
            return True
        if open_tag == "optgroup" and new_tag == "optgroup":
            return True
        if open_tag in {"td", "th"} and new_tag in {
            "td", "th", "tr", "tbody", "thead", "tfoot",
        }:
            return True
        if open_tag == "tr" and new_tag in {"tr", "tbody", "thead", "tfoot"}:
            return True
        if open_tag in {"tbody", "thead", "tfoot"} and new_tag in {
            "tbody", "thead", "tfoot",
        }:
            return True
        return False

    @staticmethod
    def _implicitly_closed_by_end(open_tag: str, end_tag: str) -> bool:
        return (
            (open_tag == "p" and end_tag in {"address", "article", "aside", "blockquote", "body", "div", "footer", "form", "header", "main", "nav", "section"})
            or (open_tag == "li" and end_tag in {"menu", "ol", "ul"})
            or (open_tag in {"dd", "dt"} and end_tag == "dl")
            or (open_tag in {"rp", "rt"} and end_tag == "ruby")
            or (open_tag == "option" and end_tag in {"optgroup", "select"})
            or (open_tag == "optgroup" and end_tag == "select")
            or (open_tag in {"td", "th"} and end_tag in {"tr", "tbody", "thead", "tfoot", "table"})
            or (open_tag == "tr" and end_tag in {"tbody", "thead", "tfoot", "table"})
            or (open_tag in {"tbody", "thead", "tfoot"} and end_tag == "table")
        )

    @staticmethod
    def _implicit_start_boundaries(new_tag: str) -> set[str]:
        if new_tag == "li":
            return {"menu", "ol", "ul"}
        if new_tag in {"dd", "dt"}:
            return {"dl"}
        if new_tag in {"option", "optgroup"}:
            return {"datalist", "select"}
        if new_tag in {"rp", "rt"}:
            return {"ruby"}
        if new_tag in {"td", "th"}:
            return {"table", "tr"}
        if new_tag in {"tr", "tbody", "thead", "tfoot"}:
            return {"table"}
        return set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if self._ambiguous_markup:
            return
        boundaries = self._implicit_start_boundaries(tag)
        boundary = max(
            (
                index
                for index, (open_tag, _, _) in enumerate(self._skip_stack)
                if open_tag in boundaries
            ),
            default=-1,
        )
        implicit_match = next(
            (
                index
                for index in range(len(self._skip_stack) - 1, boundary, -1)
                if self._implicitly_closed_by_start(self._skip_stack[index][0], tag)
            ),
            None,
        )
        if implicit_match is not None:
            while len(self._skip_stack) > implicit_match:
                self._pop_top()
        attrs_map = {name.lower(): (value or "") for name, value in attrs}
        classes = set(attrs_map.get("class", "").split())
        presentation_style = ";".join(
            f"{name}:{value}"
            for name, value in attrs_map.items()
            if name in self._PRESENTATION_STYLE_ATTRS
        )
        inline_hidden, inline_ambiguous = _style_state(
            attrs_map.get("style", ""),
            fail_closed=self._fail_closed,
            replaced_element=tag in self._REPLACED_TAGS,
            custom_properties=self._custom_properties,
        )
        presentation_hidden, presentation_ambiguous = _style_state(
            presentation_style,
            fail_closed=self._fail_closed,
            replaced_element=tag in self._REPLACED_TAGS,
        )
        svg_position_hidden, svg_position_ambiguous = self._svg_position_state(
            tag,
            attrs_map,
        )
        known_hidden = (
            tag in self._skip_tags
            or tag in self._hidden_tags
            or "*" in self._hidden_tags
            or any(
                name in attrs_map
                and (expected is None or attrs_map[name] == expected)
                for name, expected in self._hidden_attrs
            )
            or "hidden" in attrs_map
            or (
                not self._residue_mode
                and attrs_map.get("aria-hidden", "").lower() == "true"
            )
            or bool(classes & self._hidden_classes)
            or attrs_map.get("id", "") in self._hidden_ids
            or inline_hidden
            or (self._fail_closed and presentation_hidden)
            or (self._fail_closed and svg_position_hidden)
            or (
                self._fail_closed
                and attrs_map.get("fill", "").strip().lower() == "none"
            )
            or (
                self._fail_closed
                and _is_zero_css_value(attrs_map.get("fill-opacity", ""))
            )
        )
        css_ambiguous = (
            tag in self._ambiguous_tags
            or "*" in self._ambiguous_tags
            or any(
                name in attrs_map
                and (expected is None or attrs_map[name] == expected)
                for name, expected in self._ambiguous_attrs
            )
            or bool(classes & self._ambiguous_classes)
            or attrs_map.get("id", "") in self._ambiguous_ids
        )
        if known_hidden or (self._skip_depth and not self._ambiguous_depth):
            inline_ambiguous = False
            presentation_ambiguous = False
            svg_position_ambiguous = False
            css_ambiguous = False
        current_ambiguous = self._fail_closed and (
            css_ambiguous
            or inline_ambiguous
            or presentation_ambiguous
            or svg_position_ambiguous
        )
        ambiguous_hidden = (
            current_ambiguous and not known_hidden and self._skip_depth == 0
        )
        if not known_hidden and (self._ambiguous_depth or ambiguous_hidden):
            self._handle_ambiguous_starttag(tag, attrs)
        hidden = known_hidden or current_ambiguous
        is_void = tag in self._VOID_TAGS
        if not is_void:
            self._skip_stack.append((tag, hidden, ambiguous_hidden))
            if tag == "svg":
                self._svg_viewports.append(
                    self._svg_viewport(attrs_map) or (0.0, 0.0, 4096.0, 4096.0)
                )
            if hidden:
                self._skip_depth += 1
            if ambiguous_hidden:
                self._ambiguous_depth += 1
        if hidden or self._skip_depth:
            return
        self._handle_visible_starttag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self._ambiguous_markup:
            return
        if tag in self._VOID_TAGS:
            return
        match = next(
            (index for index in range(len(self._skip_stack) - 1, -1, -1)
             if self._skip_stack[index][0] == tag),
            None,
        )
        if match is None:
            return
        if match != len(self._skip_stack) - 1:
            intervening = self._skip_stack[match + 1:]
            if not intervening or not self._implicitly_closed_by_end(
                intervening[0][0],
                tag,
            ):
                self._mark_ambiguous()
                return
        closing = self._skip_stack[match:]
        del self._skip_stack[match:]
        for open_tag, _, _ in reversed(closing):
            if open_tag == "svg" and self._svg_viewports:
                self._svg_viewports.pop()
        self._skip_depth = max(
            0,
            self._skip_depth - sum(1 for _, hidden, _ in closing if hidden),
        )
        self._ambiguous_depth = max(
            0,
            self._ambiguous_depth
            - sum(1 for _, _, ambiguous in closing if ambiguous),
        )

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        # In HTML, a trailing slash is ignored on non-void elements. Treating
        # <div hidden/> as closed would expose everything that follows even
        # though browsers and WeasyPrint keep it inside the hidden div.
        foreign_svg = tag.lower() == "svg" or bool(self._svg_viewports)
        self.handle_starttag(tag, attrs)
        if foreign_svg and tag.lower() not in self._VOID_TAGS:
            self.handle_endtag(tag)

    def handle_data(self, data: str) -> None:
        if self._ambiguous_markup:
            if not self._fail_closed:
                self._handle_visible_data(data)
        elif self._ambiguous_depth:
            self._handle_ambiguous_data(data)
        elif self._skip_depth == 0:
            self._handle_visible_data(data)

    def _handle_visible_starttag(
        self, _tag: str, _attrs: list[tuple[str, str | None]],
    ) -> None:
        return

    def _handle_ambiguous_starttag(
        self,
        _tag: str,
        _attrs: list[tuple[str, str | None]],
    ) -> None:
        return

    def _handle_ambiguous_data(self, _data: str) -> None:
        return

    def _handle_visible_data(self, _data: str) -> None:
        return


class _VisibleTextParser(_HtmlVisibilityParser):
    """Extract visible text from filled HTML while skipping code-like blocks."""

    _SKIP_TAGS = {
        "clippath", "code", "datalist", "defs", "desc", "head", "mask",
        "metadata", "noembed", "noframes", "noscript", "pattern", "pre", "rp",
        "script", "style", "symbol", "template", "title",
    }
    def __init__(
        self,
        hidden_classes: set[str],
        hidden_ids: set[str],
        hidden_tags: set[str],
        hidden_attrs: set[tuple[str, str | None]],
        ambiguous_classes: set[str],
        ambiguous_ids: set[str],
        ambiguous_tags: set[str],
        ambiguous_attrs: set[tuple[str, str | None]],
        visibility_ambiguous: bool,
        *,
        fail_closed: bool,
        residue_mode: bool = False,
        custom_properties: dict[str, str] | None = None,
    ) -> None:
        super().__init__(
            hidden_classes,
            hidden_ids,
            hidden_tags,
            hidden_attrs,
            ambiguous_classes,
            ambiguous_ids,
            ambiguous_tags,
            ambiguous_attrs,
            visibility_ambiguous,
            skip_tags=self._SKIP_TAGS,
            fail_closed=fail_closed,
            residue_mode=residue_mode,
            custom_properties=custom_properties,
        )
        self.parts: list[str] = []

    def _handle_visible_data(self, data: str) -> None:
        self.parts.append(data)

    def _handle_ambiguous_data(self, data: str) -> None:
        if data.strip():
            self._visibility_ambiguous = True


def visible_html_evidence(
    raw: str,
    *,
    fail_closed: bool = False,
    residue_mode: bool = False,
) -> tuple[str, bool]:
    custom_properties = _document_custom_properties(raw)
    css_filters = (
        _css_hidden_filters(
            raw,
            fail_closed=fail_closed,
            custom_properties=custom_properties,
        )
        if not residue_mode
        else (set(), set(), set(), set(), set(), set(), set(), set(), False)
    )
    parser = _VisibleTextParser(
        *css_filters,
        fail_closed=fail_closed,
        residue_mode=residue_mode,
        custom_properties=custom_properties,
    )
    parser.feed(raw)
    if fail_closed and parser._ambiguous_markup:
        return "", True
    return "\n".join(parser.parts), parser._visibility_ambiguous


def visible_html_text(
    raw: str,
    *,
    fail_closed: bool = False,
    residue_mode: bool = False,
) -> str:
    return visible_html_evidence(
        raw,
        fail_closed=fail_closed,
        residue_mode=residue_mode,
    )[0]
