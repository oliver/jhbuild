# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2001-2006  James Henstridge
#
#   perl.py: perl module type definitions.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

__metaclass__ = type

import os
import re

from jhbuild.errors import BuildStateError
from jhbuild.modtypes import \
     Package, DownloadableModule, get_dependencies, get_branch, register_module_type

__all__ = [ 'PerlModule' ]

class PerlModule(Package, DownloadableModule):
    """Base type for modules that are distributed with a Perl style
    "Makefile.PL" Makefile."""
    type = 'perl'

    PHASE_CHECKOUT = DownloadableModule.PHASE_CHECKOUT
    PHASE_FORCE_CHECKOUT = DownloadableModule.PHASE_FORCE_CHECKOUT
    PHASE_BUILD = 'build'
    PHASE_INSTALL = 'install'

    def __init__(self, name, branch, makeargs='',
                 dependencies=[], after=[], suggests=[]):
        Package.__init__(self, name, dependencies, after, suggests)
        self.branch = branch
        self.makeargs = makeargs

    def get_srcdir(self, buildscript):
        return self.branch.srcdir

    def get_builddir(self, buildscript):
        # does not support non-srcdir builds
        return self.get_srcdir(buildscript)

    def get_revision(self):
        return self.branch.branchname

    def do_build(self, buildscript):
        buildscript.set_action(_('Building'), self)
        builddir = self.get_builddir(buildscript)
        perl = os.environ.get('PERL', 'perl')
        make = os.environ.get('MAKE', 'make')
        makeargs = self.makeargs + ' ' + self.config.module_makeargs.get(
                self.name, self.config.makeargs)
        cmd = '%s Makefile.PL INSTALLDIRS=vendor PREFIX=%s %s' % (perl, buildscript.config.prefix, makeargs)
        buildscript.execute(cmd, cwd=builddir, extra_env = self.extra_env)
        buildscript.execute([make, 'LD_RUN_PATH='], cwd=builddir,
                extra_env = self.extra_env)
    do_build.depends = [PHASE_CHECKOUT]
    do_build.error_phases = [PHASE_FORCE_CHECKOUT]

    def do_install(self, buildscript):
        buildscript.set_action(_('Installing'), self)
        builddir = self.get_builddir(buildscript)
        make = os.environ.get('MAKE', 'make')
        buildscript.execute(
                [make, 'install', 'PREFIX=%s' % buildscript.config.prefix],
                cwd = builddir, extra_env = self.extra_env)
        buildscript.packagedb.add(self.name, self.get_revision() or '')
    do_install.depends = [PHASE_BUILD]

    def xml_tag_and_attrs(self):
        return 'perl', [('id', 'name', None),
                         ('makeargs', 'makeargs', '')]


def parse_perl(node, config, uri, repositories, default_repo):
    id = node.getAttribute('id')
    makeargs = ''
    if node.hasAttribute('makeargs'):
        makeargs = node.getAttribute('makeargs')

    # Make some substitutions; do special handling of '${prefix}'
    p = re.compile('(\${prefix})')
    makeargs = p.sub(config.prefix, makeargs)
    
    dependencies, after, suggests = get_dependencies(node)
    branch = get_branch(node, repositories, default_repo, config)

    return PerlModule(id, branch, makeargs,
            dependencies=dependencies, after=after,
            suggests=suggests)
register_module_type('perl', parse_perl)

