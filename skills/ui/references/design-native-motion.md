# Native Motion Mapping

Load when the surface is a native app (SwiftUI, UIKit, Jetpack Compose) rather than a web page. The motion judgment in `design-reference.md` is platform-independent: frequency decides whether something animates, duration follows the element, and activation gets acknowledged. Native idioms differ; inspect the control's actual state feedback before adding motion.

## Translating the web idioms

| Web | SwiftUI |
|---|---|
| `transition: transform 200ms ease-out` | `.animation(.easeOut(duration: 0.2), value: someState)` |
| `cubic-bezier(0.16, 1, 0.3, 1)` | `.timingCurve(0.16, 1, 0.3, 1, duration: 0.2)` |
| `transition-property` specificity | `.animation(_:value:)` bound to one value; a bare `.animation(_)` is the `transition: all` of SwiftUI |
| `:active { transform: scale(0.96) }` | a `ButtonStyle` reading `configuration.isPressed` |
| `transform-origin` | `.scaleEffect(_:anchor:)` |
| `prefers-reduced-motion` | `@Environment(\.accessibilityReduceMotion)` |
| spring `{ duration, bounce }` | `.spring(duration:bounce:)`, or `.spring(response:dampingFraction:)` on older deployment targets |
| `nth-child` stagger delay | `.delay(Double(index) * 0.04)` on the row's animation |
| `will-change` | `.drawingGroup()`, and only after measuring a real dropped frame |

Interruptibility inverts between the two. On the web you reach for transitions over keyframes to get retargeting; in SwiftUI, value-driven animation already retargets from its current position, and the things that do not are `.repeatForever`, `KeyframeAnimator`, and any animation driven by a timer instead of by state.

## Where native surfaces actually break

- **Press is unacknowledged.** Hover cannot confirm activation. An immediate selected, open, or loading state can; inspect the result before adding a press effect. A hover/press count mismatch alone proves no defect, and instant or high-frequency controls need no extra movement.
- **The reflex curve is symmetric.** `.easeInOut` is what gets typed when no decision was made. It is correct for something moving or morphing in place and wrong for anything entering, exiting, or responding to input, which is most of an app.
- **Reduced motion deletes the signal.** Disable the movement or scale itself, not only its interpolation; a transform with no animation still jumps. A pulsing or sliding progress indicator that simply freezes reads as a hang. Keep a still form of the same signal (a determinate step, a text state) instead of removing it.
- **Literals outlive the token layer.** Named motion constants get added, then new views keep typing `0.18` inline because it is one character shorter than reaching for the token. Grep for raw curve constructors outside the token file; the count going up is the drift signal. The point is not tidiness, it is that retuning the app's feel should be one edit rather than a survey.
- **A motion token is a sentence, not a number.** `expandCollapse` says where it is allowed; `0.15` says nothing and gets copied into places it does not fit. Name each token for the interaction and record why the value cannot be faster or slower, because that reason is what a later reader needs in order to change it safely.

A motion or icon change is verified by looking: two frames captured during the transition (or a short recording) and one still of the icon at the shipped size, attached or described. "Added" without a capture is a claim.

The same mapping shape holds for UIKit (`UIViewPropertyAnimator`, `isHighlighted`, `UIAccessibility.isReduceMotionEnabled`) and Compose (`animate*AsState`, `InteractionSource.collectIsPressedAsState`, `LocalAccessibilityManager`). Translate the row, keep the judgment.
