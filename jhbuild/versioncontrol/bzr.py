# jhbuild - a build script for GNOME 1.x and 2.x
# Copyright (C) 2001-2006  James Henstridge
#
#   bzr.py: some code to handle various bazaar-ng operations
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

__all__ = []
__metaclass__ = type

import os
import errno
import urlparse
import logging

from jhbuild.errors import FatalError, CommandError
from jhbuild.utils.cmds import get_output
from jhbuild.versioncontrol import Repository, Branch, register_repo_type
from jhbuild.commands.sanitycheck import inpath
from jhbuild.utils.sxml import sxml

# Make sure that the urlparse module considers bzr://, bzr+ssh://, sftp:// and lp:
# scheme to be netloc aware and set to allow relative URIs.
if 'bzr' not in urlparse.uses_netloc:
    urlparse.uses_netloc.append('bzr')
if 'bzr' not in urlparse.uses_relative:
    urlparse.uses_relative.append('bzr')
if 'bzr+ssh' not in urlparse.uses_netloc:
    urlparse.uses_netloc.append('bzr+ssh')
if 'bzr+ssh' not in urlparse.uses_relative:
    urlparse.uses_relative.append('bzr+ssh')
if 'sftp' not in urlparse.uses_netloc:
    urlparse.uses_netloc.append('sftp')
if 'sftp' not in urlparse.uses_relative:
    urlparse.uses_relative.append('sftp')
if 'lp' not in urlparse.uses_relative:
    urlparse.uses_relative.append('lp')


class BzrRepository(Repository):
    """A class representing a Bzr repository.

    It can be a parent of a number of Bzr repositories or branches.
    """

    init_xml_attrs = ['href', 'trunk-template', 'branches-template']

    def __init__(self, config, name, href, trunk_template='%(module)s', branches_template='%(module)s/%(branch)s'):
        Repository.__init__(self, config, name)
        # allow user to adjust location of branch.
        self.href = config.repos.get(name, href)
        self.trunk_template = trunk_template
        self.branches_template = branches_template

    branch_xml_attrs = ['module', 'checkoutdir', 'revision', 'tag', 'user', 'revspec', 'branch']

    def branch(self, name, module=None, checkoutdir=None, revision=None,
               tag=None, user=None, revspec=None, branch=None, module_href=None):
        if name in self.config.branches:
            module_href = self.config.branches[name]
            if not module_href:
                raise FatalError(_('branch for %s has wrong override, check your .jhbuildrc') % name)

        if module is None:
            module = name

        if revision or branch:
            template = urlparse.urljoin(self.href, self.branches_template)
        else:
            template = urlparse.urljoin(self.href, self.trunk_template)

        if not module_href:
            module_href = template % {
                'module': module,
                'revision': revision,
                'branch': branch,
                'tag' : tag,
                'user': user,
            }

        if checkoutdir is None:
            checkoutdir = name

        return BzrBranch(self, module_href, checkoutdir, tag, revspec)

    def to_sxml(self):
        return [sxml.repository(type='bzr', name=self.name, href=self.href,
                    trunk=self.trunk_template, branches=self.branches_template)]

class BzrBranch(Branch):
    """A class representing a Bazaar branch."""

    def __init__(self, repository, module_href, checkoutdir, tag, revspec):
        Branch.__init__(self, repository, module_href, checkoutdir)
        self._revspec = None
        self.revspec = (tag, revspec)

    def get_revspec(self):
        return self._revspec

    def set_revspec(self, (tag, revspec)):
        if revspec:
            self._revspec = ['-r%s' % revspec]
        elif tag:
            logging.info('tag ' + _('attribute is deprecated. Use revspec instead.'))
            self._revspec = ['-rtag:%s' % tag]
        elif self.config.sticky_date:
            self._revspec = ['-rdate:%s' % self.config.sticky_date]
        else:
            self._revspec = []
    revspec = property(get_revspec, set_revspec)

    def srcdir(self):
        return Branch.get_checkoutdir(self)

    srcdir = property(srcdir)

    def get_module_basename(self):
        return self.checkoutdir

    def branchname(self):
        try:
            return get_output(['bzr', 'nick', self.srcdir])
        except:
            return None
    branchname = property(branchname)

    def exists(self):
        try:
            get_output(['bzr', 'ls', self.module])
            return True
        except:
            return False

    def create_mirror(self, buildscript):
        if not self.config.dvcs_mirror_dir:
            return
        if self.config.nonetwork:
            return

        if not os.path.exists(os.path.join(self.config.dvcs_mirror_dir, '.bzr')):
            cmd = ['bzr', 'init-repo', '--no-trees', self.config.dvcs_mirror_dir]
            buildscript.execute(cmd)

        local_mirror = os.path.join(self.config.dvcs_mirror_dir, self.checkoutdir)

        if not os.path.exists(local_mirror):
            cmd = ['bzr', 'init', '--create-prefix', local_mirror]
            buildscript.execute(cmd)

        if os.path.exists(self.srcdir):
            cmd = ['bzr', 'info', self.srcdir]
            cwd = self.config.dvcs_mirror_dir
            try:
                info = get_output(cmd, cwd=cwd)
                if info.find('checkout of branch: %s' % self.checkoutdir) == -1:
                    raise NameError
            except:
                raise FatalError(_("""
Path %s does not seem to be a checkout from dvcs_mirror_dir.
Remove it or change your dvcs_mirror_dir settings.""") % self.srcdir)

        else:
            cmd = ['bzr', 'co', '--light', mirror_href, self.srcdir]
            buildscript.execute(cmd)

    def _checkout(self, buildscript, copydir=None):
        if self.config.dvcs_mirror_dir:
            self.create_mirror(buildscript)
            self.real_update(buildscript)
        else:
            cmd = ['bzr', 'branch'] + self.revspec + [self.module, self.srcdir]
            buildscript.execute(cmd)

    def _export(self, buildscript):
        cmd = ['bzr', 'export'] + self.revspec + [self.srcdir, self.module]
        buildscript.execute(cmd)

    def real_update(self, buildscript):
        cmd = ['bzr', 'pull'] + self.revspec + [self.module, '-d', self.srcdir]
        buildscript.execute(cmd)
        cmd = ['bzr', 'update'] + self.revspec + [self.srcdir]

    def _update(self, buildscript, copydir=None):
        self.create_mirror(buildscript)
        self.real_update(buildscript)

    def checkout(self, buildscript):
        if not inpath('bzr', os.environ['PATH'].split(os.pathsep)):
            raise CommandError(_('%s not found') % 'bzr')
        Branch.checkout(self, buildscript)

    def tree_id(self):
        if not os.path.exists(self.srcdir):
            return None
        else:
            try:
                # --tree is relatively new (bzr 1.17)
                cmd = ['bzr', 'revision-info', '--tree']
                tree_id = get_output(cmd, cwd=self.srcdir).strip()
            except:
                cmd = ['bzr', 'revision-info']
                tree_id = get_output(cmd, cwd=self.srcdir).strip()
            return tree_id

    def to_sxml(self):
        attrs = {}
        if self.revspec:
            attrs = self.revspec()[0]
        return [sxml.branch(repo=self.repository.name,
                            module=self.module,
                            revid=self.tree_id(),
                            **attrs)]

register_repo_type('bzr', BzrRepository)
