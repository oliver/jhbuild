# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2001-2006  James Henstridge
#
#   arch.py: some code to handle various arch operations
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
__all__ = []

import os, sys

from jhbuild.errors import FatalError, BuildStateError, CommandError
from jhbuild.utils.cmds import get_output
from jhbuild.versioncontrol import Repository, Branch, register_repo_type
from jhbuild.commands.sanitycheck import inpath

def is_registered(archive):
    location = os.path.join(os.environ['HOME'], '.arch-params',
                            '=locations', archive)
    return os.path.exists(location)

def register(archive, uri):
    if not is_registered(archive):
        assert uri is not None, 'can not register archive without uri'
        res = os.system('baz register-archive %s' % uri)
        if res != 0:
            raise jhbuild.errors.FatalError(_('could not register archive %s')
                                            % archive)

def get_version(directory):
    '''Gets the tree version for a particular directory.'''
    data = get_output(['baz', 'tree-version', '-d', directory])
    archive, version = data.strip().split('/')
    return archive, version

def split_name(version):
    '''Returns an (archive, version) pair for the string passed in.  If
    no archive is mentioned, use the default archive name.'''
    if '/' in version:
        (archive, version) = version.split('/')
    else:
        # no archive specified -- use default.
        archive = open(os.path.join(os.environ['HOME'], '.arch-params',
                                    '=default-archive'), 'r').read().strip()
    return (archive, version)


class ArchRepository(Repository):
    """A class representing an Arch archive."""

    init_xml_attrs = ['archive', 'href']

    def __init__(self, config, name, archive, href=None):
        Repository.__init__(self, config, name)
        self.archive = archive
        self.href = href

    def _ensure_registered(self):
        # has the archive been registered?
        location = os.path.join(os.environ['HOME'], '.arch-params',
                                '=locations', self.archive)
        is_registered = os.path.exists(location)
        if is_registered:
            return

        if self.href is None:
            raise BuildStateError(_('archive %s not registered') % self.href)
        res = os.system('baz register-archive %s' % self.href)
        if res != 0:
            raise BuildStateError(_('could not register archive %s')
                                  % self.archive)

    branch_xml_attrs = ['module', 'checkoutdir']

    def branch(self, name, module=None, checkoutdir=None):
        if name in self.config.branches:
            module = self.config.branches[name]
            if not module:
                raise FatalError(_('branch for %s has wrong override, check your .jhbuildrc') % name)
        else:
            if module is None:
                module = name
            module = '%s/%s' % (self.archive, module)
        return ArchBranch(self, module, checkoutdir)


class ArchBranch(Branch):
    """A class representing an Arch branch"""

    def srcdir(self):
        if self.checkoutdir:
            return os.path.join(self.checkoutroot, self.checkoutdir)
        else:
            return os.path.join(self.checkoutroot,
                                os.path.basename(self.module))
    srcdir = property(srcdir)

    def branchname(self):
        return self.module
    branchname = property(branchname)

    def _checkout(self, buildscript):
        # if the archive name hasn't been overridden, ensure that it
        # has been registered.
        archive, version = split_name(self.module)
        if archive == self.repository.archive:
            self.repository._ensure_registered()
        
        cmd = ['baz', 'get', self.module]

        if checkoutdir:
            cmd.append(checkoutdir)

        if date:
            raise BuildStageError(_('date based checkout not yet supported\n'))

        buildscript.execute(cmd, 'arch', cwd=self.checkoutroot)

    def _update(self, buildscript):
        '''Perform a "baz update" (or possibly a checkout)'''
        # if the archive name hasn't been overridden, ensure that it
        # has been registered.
        archive, version = split_name(self.module)
        if archive == self.repository.archive:
            self.repository._ensure_registered()

        if date:
            raise BuildStageError(_('date based checkout not yet supported\n'))

        archive, version = split_name(self.module)
        # how do you move a working copy to another branch?
        wc_archive, wc_version = get_version(self.srcdir)
        if (wc_archive, wc_version) != (archive, version):
            cmd = ['baz', 'switch', self.module]
        else:
            cmd = ['baz', 'update']

        buildscript.execute(cmd, 'arch', cwd=self.srcdir)

    def checkout(self, buildscript):
        if not inpath('arch', os.environ['PATH'].split(os.pathsep)):
            raise CommandError(_('%s not found') % 'arch')
        Branch.checkout(self, buildscript)

    def tree_id(self):
        if not os.path.exists(self.srcdir):
            return None
        data = get_output(['baz', 'tree-id', '-d', self.srcdir], cwd = self.srcdir)
        return data.strip()



register_repo_type('arch', ArchRepository)
