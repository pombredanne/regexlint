#!/usr/bin/env python2
#
# Copyright 2011-2012 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import sys
import re
import logging

from pygments.lexer import RegexLexer, bygroups
from pygments.token import Token
from regexlint import Regex, run_all_checkers
from regexlint.checkers import manual_check_for_empty_string_match
from regexlint.indicator import find_offending_line, mark, find_substr_pos
from regexlint.util import consistent_repr, shorten

def import_mod(m):
    mod = __import__(m)
    for part in m.split('.')[1:]:
        mod = getattr(mod, part)
    return mod

def main(argv):
    import optparse
    o = optparse.OptionParser()
    o.add_option('--min_level',
                 help='Min level to print (logging constant names like ERROR)',
                 default='WARNING')
    opts, args = o.parse_args(argv)

    min_level = getattr(logging, opts.min_level)

    # currently just a list of module names.
    for module in args:
        if ':' in module:
            module, cls = module.split(':')
        else:
            cls = None
        mod = import_mod(module)
        print "Module", module
        if cls:
            lexers = [cls]
        else:
            if hasattr(mod, '__all__'):
                lexers = mod.__all__
            else:
                lexers = mod.__dict__.keys()

        check_lexers(mod, lexers, min_level=min_level)

def check_lexers(mod, lexer_names, min_level):
    for k in lexer_names:
        v = getattr(mod, k)
        if hasattr(v, '__bases__') and issubclass(v, RegexLexer) and v.tokens:
            check_lexer(k, v, mod.__file__, min_level)

def remove_error(errs, *nums):
    for i in range(len(errs)-1, -1, -1):
        if errs[i][0] in nums:
            del errs[i]

def check_lexer(lexer_name, cls, mod_path, min_level):
    #print lexer_name
    #print cls().tokens
    has_errors = False

    bygroups_callback = bygroups(1).func_code
    for state, pats in cls().tokens.iteritems():
        for i, pat in enumerate(pats):
            #print repr(pat[0])
            try:
                reg = Regex.get_parse_tree(pat[0], cls.flags)
            except:
                print pat[0], cls
                raise
            # Special problem: display an error if count of args to
            # bygroups(...) doesn't match the number of capture groups
            if callable(pat[1]) and pat[1].func_code is bygroups_callback:
                by_groups = pat[1].func_closure[0].cell_contents
            else:
                by_groups = None

            errs = run_all_checkers(reg, by_groups)
            # Special case for empty string, since it needs action.
            manual_check_for_empty_string_match(reg, errs, pat)

            errs.sort(key=lambda k: (k[1], k[0]))
            if errs:
                #print "Errors in", lexer_name, state, "pattern", i
                for num, severity, pos1, text in errs:
                    if severity < min_level: continue

                    # Only set this if we're going to output something --
                    # otherwise the [Lexer] OK won't print
                    has_errors = True

                    foo = find_offending_line(mod_path, lexer_name, state, i,
                                              pos1)
                    if foo:
                        line = 'L' + str(foo[0])
                    else:
                        line = 'pat#' + str(i+1)
                    print '%s%s:%s:%s:%s: %s' % (
                        logging.getLevelName(severity)[0], num,
                        lexer_name, state, line, text)
                    if foo:
                        mark(*foo)
                    else:
                        # Substract one for closing quote
                        start = len(consistent_repr(pat[0][:pos1])) - 1
                        end = len(consistent_repr(pat[0][:pos1+1])) - 1
                        if start == end:
                            # This handles the case where pos1 points to the end
                            # of the string. Regex "|" with pos1 = 1.
                            end += 1
                        assert end > start
                        text, start, end = shorten(repr(pat[0]), start, end)
                        mark(-1, start, end, text)
    if not has_errors:
        print lexer_name, "OK"


if __name__ == '__main__':
    main(sys.argv[1:])
