#!/usr/bin/env python

# Copyright (c) 2014-2015, Ericsson AB. All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification,
# are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
# list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice, this
# list of conditions and the following disclaimer in the documentation and/or other
# materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
# IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT,
# INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT
# NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
# PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY
# OF SUCH DAMAGE.

import re
import os
import sys
import errno
import copy
import argparse
import xml.etree.ElementTree as ET
import config

 ######   #######  ##    ##  ######  ########
##    ## ##     ## ###   ## ##    ##    ##
##       ##     ## ####  ## ##          ##
##       ##     ## ## ## ##  ######     ##
##       ##     ## ##  ####       ##    ##
##    ## ##     ## ##   ### ##    ##    ##
 ######   #######  ##    ##  ######     ##

parser = argparse.ArgumentParser()
parser.add_argument('--gir', nargs = '+', dest = 'gir', metavar = 'FILE', help = '.gir file')
parser.add_argument('--c-out', dest = 'c_path', metavar = 'DIR', help = '.c output file')
parser.add_argument('--j-out', dest = 'j_dir', metavar = 'DIR', help = '.java base output directory')
parser.add_argument('--headers', nargs = '+', dest = 'headers', metavar = 'HEADERS', help = '.h files to include')
parser.add_argument('--package-root', dest = 'package_root', metavar = 'PACKAGE_ROOT',
                    help = 'the Java package root for generated code')
parser.add_argument('--log-tag', dest = 'log_tag', metavar = 'LOG_TAG',
                    help = 'the Android log tag to use in debug output')
args = parser.parse_args()

if args.gir:
    print 'reading from gir files "{}"'.format(args.gir)
else:
    print 'missing gir input file (--gir)'
if args.c_path:
    print 'saving generated C source to "{}"'.format(args.c_path)
else:
    print 'missing C output file (--c-out)'
if args.j_dir:
    print 'saving generated Java source in "{}"'.format(args.j_dir)
else:
    print 'missing Java output directory (--j-out)'
if args.package_root:
    print 'package root is: "{}"'.format(args.package_root)
    config.PACKAGE_ROOT = args.package_root
else:
    print 'missing package root (--package-root)'
if args.log_tag:
    print 'log tag is: "{}"'.format(args.log_tag)
    config.LOG_TAG = args.log_tag
else:
    print 'missing log tag (--log-tag)'

args.c_dir, args.c_file = os.path.split(args.c_path)
if not args.c_file:
    print('no filename given for C source')
    sys.exit(-1)

if not all(args.__dict__.values()):
    print "all arguments must be set"
    sys.exit(-1)

def write_file(content, path, filename):
    try:
        os.makedirs(path)
    except OSError as e:
        if e.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise
    outfile = open(path + os.sep + filename, 'w')
    outfile.write(content)
    outfile.close()


# These are imported after argument parsing so we can set package root and log tag
import c_generator
import java_generator
from c_generator import C
from gir_parser import GirParser
from type_registry import TypeRegistry
from type_registry import TypeTransform
from type_registry import GirMetaType
from standard_types import standard_types
from standard_types import ObjectMetaType


HEADERS = [
    'android/native_window_jni.h',
]

class WindowHandleType(ObjectMetaType(
        gir_type='WindowHandle',
        java_type='Surface',
        c_type='OwrWindowHandle',
        package='android.view',
    )):

    def transform_to_c(self):
        return TypeTransform([
            C.Decl(self.c_type, self.c_name),
        ],[
            C.Assign(self.c_name, C.Call('ANativeWindow_fromSurface', 'env', self.jni_name)),
        ])


def remove_ignored_elements(xml_root):
    def remove_elem(path):
        parent = xml_root.find(path + '/..')
        elem = xml_root.find(path)
        if parent is not None:
            parent.remove(elem)
        else:
            print('ignored element was not found: ' + path)
    [remove_elem(path) for path in config.IGNORED_ELEMENTS]


def main(argv = None):
    if argv is None:
        argv = sys.argv

    print('-------- BEGIN ---------')

    type_registry = TypeRegistry()
    type_registry.register(standard_types)
    type_registry.register(WindowHandleType)

    for gir in args.gir:
        xml_root = ET.parse(gir).getroot()
        remove_ignored_elements(xml_root)
        gir_parser = GirParser(xml_root)
        type_registry.register(gir_parser.parse_types())
        type_registry.register_enum_aliases(gir_parser.parse_enum_aliases())
        type_registry.register_ignored_types(gir_parser.parse_ignored_types())

    namespaces = gir_parser.parse_full(type_registry)

    java_base_dir = '/'.join([args.j_dir] + config.PACKAGE_ROOT.split('.'))
    for name, source in java_generator.standard_classes.items():
        write_file(source, java_base_dir, name + '.java')

    for namespace in namespaces:
        classes = java_generator.gen_namespace(namespace)
        java_namespace_dir = java_base_dir + '/' + namespace.symbol_prefix

        for name, source in classes.items():
            write_file(source, java_namespace_dir, name + '.java')

    source = c_generator.gen_source(namespaces, HEADERS + args.headers)

    write_file(source, args.c_dir, args.c_file)
    print('--------  END  ---------')


if __name__ == "__main__":
    sys.exit(main())
