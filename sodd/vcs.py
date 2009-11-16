"""Interface to VCS with some basic operations.

see HG class as interface reference and documentation.
tests make sure all implementations follow the same API.
"""

import os
import shutil
import subprocess
from xml.dom import minidom

def check_call_get(cmd):
    """Run command and return stdout, raise Exception if cmd fails"""
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    out = proc.communicate()[0]
    if proc.returncode:
        raise subprocess.CalledProcessError(proc.returncode, cmd)
    return out


# tested with hg 1.3.1
class HG(object):
    """interface to HG (mercurial)

    @ivar work_path (str): path where a working copy of the repository will
                           be created/used.
    """
    rev_zero = 0 # number of first revision
    def __init__(self, source, work_path):
        self.source = source
        self.work_path = work_path


    @staticmethod
    def is_repo(path):
        """check if the 'path' is repository
        @return bool
        """
        cmd = ['hg', 'status', '--repository', path]
        return not bool(subprocess.call(cmd))


    @staticmethod
    def init(repo_path):
        """create a new repository in the given path
        @returns (str): path folder containing the repository
                        (same as destination path for DVCS)
        """
        check_call_get(['hg', 'init', repo_path])
        return repo_path


    def add(self, file_path):
        """add specified file on the next commit"""
        check_call_get(['hg','add', '--repository', self.work_path, file_path])


    def commit(self, message):
        """commit all outstanding changes"""
        check_call_get(['hg', 'commit', '--repository', self.work_path,
                        '--message', message])


    def clone(self):
        """make a copy of an existing repository

        @param force (bool): if destination (work_path) exist, the repository
        is not copied again unless it `force` is set to True
        """
        if os.path.exists(self.work_path):
            msg = "Can not clone to an existing path: %s"
            raise Exception(msg % self.work_path)
        check_call_get(['hg', 'clone', self.source, self.work_path])


    def archive(self, rev_num, dst_path):
        """create an unversioned archive of a repository revision

        # FIXME: if dst_path exists it will be completely removed
        @param rev_num(str): revision to be archived
        @param dst_path(str): destination path of the archive
        """
        if os.path.exists(dst_path):
            shutil.rmtree(dst_path)
        cmd = ['hg', 'archive', '--repository', self.work_path,
               '--rev', rev_num, dst_path]
        check_call_get(cmd)


    def tip(self):
        """show the tip revision
        @return (str): revision number
        """
        cmd = ['hg', 'tip', '--template', '{rev}\n',
               '--repository', self.work_path]
        return check_call_get(cmd).strip()


    def pull(self):
        """pull changes from source"""
        check_call_get(['hg', 'pull', '--repository', self.work_path])


    def get_new_revisions(self, from_rev):
        """return list of revisions from (from_rev:tip]
        - exclude from_rev, include tip. empty list if from_rev==tip
        @param from_rev (str)
        @return (list of dict): { 'revision': '174'
                                  'committer': 'somebody'
                                  'comment': 'commit message'}
        """
        # first update working copy
        self.pull()
        cmd = ['hg', 'log', '--rev', '%s:' % from_rev,
               '--repository', self.work_path,
               '--template', '{rev}:{author}:{desc}\n']
        out = check_call_get(cmd)
        revs = []
        # exclude first line (old tip/head)
        for line in out.splitlines()[1:]:
            rev, author, desc = line.split(':', 2)
            revs.append({'revision': rev,
                         'committer': author,
                         'comment': desc})
        return revs


# tested with svn 1.6.5
class SVN(object):
    rev_zero = 1 # number of first revision
    def __init__(self, source, work_path):
        self.source = source
        self.work_path = work_path


    @staticmethod
    def is_repo(path):
        """check if the 'path' is repository
        @return bool
        """
        cmd = ['svn', 'status', path]
        err = subprocess.Popen(cmd, stderr=subprocess.PIPE).communicate()[1]
        return not err


    @staticmethod
    def init(repo_path):
        """create a new repository in the given path
        @returns (str): path folder containing the repository
                        (same as destination path for DVCS)
        """
        source_path = repo_path + '_REPO'
        check_call_get(['svnadmin', 'create', source_path])
        full_path = "file:///" + os.path.abspath(source_path)
        check_call_get(['svn', 'checkout', full_path, repo_path])
        return full_path


    def add(self, file_path):
        """add specified file on the next commit"""
        check_call_get(['svn','add', file_path])


    def commit(self, message):
        """commit all outstanding changes"""
        check_call_get(['svn', 'commit', '--message', message,
                        self.work_path])


    def clone(self):
        """make a copy of an existing repository

        @param source (str): location of the repository to be cloned,
                             (URL or filepath)
        @param force (bool): if destination (work_path) exist, the repository
        is not copied again unless it `force` is set to True
        """
        if os.path.exists(self.work_path):
            msg = "Can not clone to an existing path: %s"
            raise Exception(msg % self.work_path)
        check_call_get(['svn', 'checkout', self.source, self.work_path])


    def archive(self, rev_num, dst_path):
        """create an unversioned archive of a repository revision

        # FIXME: if dst_path exists it will be completely removed
        @param rev_num(str): revision to be archived
        @param dst_path(str): destination path of the archive
        """
        if os.path.exists(dst_path):
            shutil.rmtree(dst_path)
        cmd = ['svn', 'export', '--force', '--revision', rev_num,
                         self.work_path, dst_path]
        check_call_get(cmd)


    def tip(self):
        """show the tip revision
        @return (str): revision number
        """
        check_call_get(['svn', 'up'])
        cmd = ['svn', 'log', '--limit', '1', '--quiet', self.work_path]
        out = check_call_get(cmd)
        for line in out.splitlines():
            if line[0] != 'r':
                continue
            # r12345 | john | 2009-11-03 00:09:25 +0800 (Tue, 03 Nov 2009)
            return line.split()[0][1:]


    def pull(self):
        """pull changes from source"""
        check_call_get(['svn', 'update', self.work_path])


    def get_new_revisions(self, from_rev):
        """return list of revisions from (from_rev:tip]
        - exclude from_rev, include tip. empty list if from_rev==tip
        @param from_rev (str)
        @return (list of dict): { 'revision': '174'
                                  'committer': 'somebody'
                                  'comment': 'commit message'}
        """
        # first update working copy
        self.pull()
        cmd = ['svn', 'log', '--xml', '--revision', '%s:HEAD' % from_rev,
               self.work_path]
        out = check_call_get(cmd)
        revs = []
        dom = minidom.parseString(out)
        for logentry in dom.getElementsByTagName('logentry'):
            author = logentry.getElementsByTagName('author')[0].firstChild.data
            msg = logentry.getElementsByTagName('msg')[0].firstChild.data
            revs.append({'revision': logentry.getAttribute('revision'),
                         'committer': author,
                         'comment': msg})
        return sorted(revs, key=lambda k: int(k['revision']))[1:]


# tested with bzr 2.0.0
class BZR(object):
    """interface to BZR (bazaar)"""
    rev_zero = 1 # number of first revision
    def __init__(self, source, work_path):
        self.source = source
        self.work_path = work_path


    @staticmethod
    def is_repo(path):
        """check if the 'path' is repository
        @return bool
        """
        cmd = ['bzr', 'status', path]
        return not bool(subprocess.call(cmd))


    @staticmethod
    def init(repo_path):
        """create a new repository in the given path
        @returns (str): path folder containing the repository
                        (same as destination path for DVCS)
        """
        check_call_get(['bzr', 'init', repo_path])
        return repo_path


    def add(self, file_path):
        """add specified file on the next commit"""
        check_call_get(['bzr','add', file_path])


    def commit(self, message):
        """commit all outstanding changes"""
        check_call_get(['bzr', 'commit', '--message', message, self.work_path])

    def clone(self):
        """make a copy of an existing repository

        @param force (bool): if destination (work_path) exist, the repository
        is not copied again unless it `force` is set to True
        """
        if os.path.exists(self.work_path):
            msg = "Can not clone to an existing path: %s"
            raise Exception(msg % self.work_path)
        check_call_get(['bzr', 'branch', self.source, self.work_path])


    def archive(self, rev_num, dst_path):
        """create an unversioned archive of a repository revision

        # FIXME: if dst_path exists it will be completely removed
        @param rev_num(str): revision to be archived
        @param dst_path(str): destination path of the archive
        """
        if os.path.exists(dst_path):
            shutil.rmtree(dst_path)
        cmd = ['bzr','export', '--revision', rev_num, dst_path, self.work_path]
        check_call_get(cmd)


    def tip(self):
        """show the tip revision
        @return (str): revision number
        """
        cmd = ['bzr', 'version-info', '--custom', '--template', '{revno}\n',
               self.work_path]
        return check_call_get(cmd).strip()


    def pull(self):
        """pull changes from source"""
        check_call_get(['bzr', 'pull', '--directory', self.work_path])


    def get_new_revisions(self, from_rev):
        """return list of revisions from (from_rev:tip]
        - exclude from_rev, include tip. empty list if from_rev==tip
        @param from_rev (str)
        @return (list of dict): { 'revision': '174'
                                  'committer': 'somebody'
                                  'comment': 'commit message'}
        """
        # first update working copy
        self.pull()
        cmd = ['bzr', 'log', '--revision=%s..' % from_rev,
               '--forward', '--line', self.work_path]
        out = check_call_get(cmd)
        revs = []
        for line in out.splitlines()[1:]:
            # TODO: bzr log --line show only the top line of commit message
            # FIXME: what if name contains space?
            line_split = line.split(" ", 3)
            # 174: eduardo 2009-10-30 xxx yyy zzz
            revs.append(
                { 'revision': line_split[0][:-1], # get first word and remove ':'
                  'committer':  line_split[1],
                  'comment': line_split[3]
                })
        return revs



def get_vcs(vcs_name, url, work_path):
    """return a VCS object"""
    vcs_map = {'svn': SVN,
               'bzr': BZR,
               'hg': HG}
    return vcs_map[vcs_name](url, work_path)
