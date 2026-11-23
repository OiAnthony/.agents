#!/usr/bin/env node
'use strict';

module.exports = require('./ryugi.cjs');

if (require.main === module) module.exports.run();
