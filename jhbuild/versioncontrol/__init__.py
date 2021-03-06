# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2001-2006  James Henstridge
#
#   __init__.py: infrastructure for plugging in version control systems
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

__all__ = [
    'Repository',
    'Branch',
    'register_repo_type',
    'get_repo_type',
    ]

__metaclass__ = type

from jhbuild.errors import FatalError, BuildStateError
import os

class Repository:
    """An abstract class representing a collection of modules."""

    # Attributes expected on the <repository> element for this type.
    # String values are passed as keyword arguments to the constructor.
    init_xml_attrs = []

    # URI of the moduleset where this repository is defined
    moduleset_uri = None

    def __init__(self, config, name):
        self.config = config
        self.name = name

    # Attributes expected on the <branch> element for this type.
    # String values are passed as keyword arguments to the branch() method.
    branch_xml_attrs = []

    def branch(self, name, **kwargs):
        """Returns a Branch object based on the given arguments."""
        raise NotImplementedError
    
    def branch_from_xml(self, name, branchnode, repositories, default_repo):
        kws = {}
        for attr in self.branch_xml_attrs:
            if branchnode.hasAttribute(attr):
                kws[attr.replace('-', '_')] = branchnode.getAttribute(attr)
        if branchnode.hasAttribute('id'):
            kws['branch_id'] = branchnode.getAttribute('id')
        return self.branch(name, **kws)

    def to_sxml(self):
        """Return an sxml representation of this repository."""
        raise NotImplementedError


class Branch:
    """An abstract class representing a branch in a repository."""

    def __init__(self, repository, module, checkoutdir):
        self.repository = repository
        self.config = repository.config
        self.module = module
        self.checkoutdir = checkoutdir
        self.checkoutroot = self.config.checkoutroot

    def get_checkout_mode(self):
        checkout_mode = self.config.checkout_mode
        return self.config.module_checkout_mode.get(self.module, checkout_mode)
    checkout_mode = property(get_checkout_mode)

    def srcdir(self):
        """Return the directory where this branch is checked out."""
        raise NotImplementedError
    srcdir = property(srcdir)

    def branchname(self):
        """Return an identifier for this branch or None."""
        raise NotImplementedError
    branchname = property(branchname)

    def exists(self):
        """Return True if branch exists or False if not.

           May raise NotImplementedError if cannot check a given branch."""
        raise NotImplementedError

    def get_module_basename(self):
        return os.path.basename(self.module)

    def get_checkoutdir(self):
        if self.checkout_mode == 'copy' and self.config.copy_dir:
            return os.path.join(self.config.copy_dir, self.get_module_basename())
        if self.checkoutdir:
            return os.path.join(self.checkoutroot, self.checkoutdir)
        else:
            return os.path.join(self.checkoutroot, self.get_module_basename())

    def may_checkout(self, buildscript):
        if buildscript.config.nonetwork:
            return False
        return True

    def checkout(self, buildscript):
        """Checkout or update the given source directory.

        May raise CommandError or BuildStateError if a problem occurrs.
        """
        if self.checkout_mode in ('clobber', 'export'):
            self._wipedir(buildscript)
            if self.checkout_mode == 'export':
                try:
                    self._export(buildscript)
                except NotImplementedError:
                    pass
                else:
                    return
            self._checkout(buildscript)
        elif self.checkout_mode in ('update', 'copy'):
            if self.checkout_mode == 'copy' and self.config.copy_dir:
                copydir = self.config.copy_dir
                if os.path.exists(self.get_checkoutdir()):
                    self._update(buildscript, self.config.copy_dir)
                else:
                    self._wipedir(buildscript)
                    self._checkout(buildscript, copydir)
                self._copy(buildscript, copydir)
            else:
                if os.path.exists(self.get_checkoutdir()):
                    self._update(buildscript)
                else:
                    self._checkout(buildscript)

    def force_checkout(self, buildscript):
        """A more agressive version of checkout()."""
        self._wipedir(buildscript)
        self.checkout(buildscript)

    def tree_id(self):
        """A string identifier for the state of the working tree."""
        raise NotImplementedError

    def _wipedir(self, buildscript):
        if os.path.exists(self.srcdir):
            buildscript.execute(['rm', '-rf', self.srcdir])

    def _export(self, buildscript):
        raise NotImplementedError

    def _copy(self, buildscript, copydir):
         module = self.module
         if self.checkoutdir:
             module = self.checkoutdir
         fromdir = os.path.join(copydir, os.path.basename(module))
         todir = os.path.join(self.config.checkoutroot, os.path.basename(module))
         if os.path.exists(todir):
             self._wipedir(buildscript)
         buildscript.execute(['cp', '-R', fromdir, todir])

    def to_sxml(self):
        """Return an sxml representation of this checkout."""
        raise NotImplementedError

_repo_types = {}
def register_repo_type(name, repo_class):
    _repo_types[name] = repo_class

def get_repo_type(name):
    if name not in _repo_types:
        try:
            __import__('jhbuild.versioncontrol.%s' % name)
        except ImportError:
            pass
    if name not in _repo_types:
        raise FatalError(_('unknown repository type %s') % name)
    return _repo_types[name]
