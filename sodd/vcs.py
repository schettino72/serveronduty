"""Interface to VCS with some basic operations"""

import os
import shutil
import subprocess


class SVN(object):
    def __init__(self, url, work_path):
        self.url = url
        self.work_path = work_path


    def clone(self):
        """SVN checkout"""
	if not os.path.exists(self.work_path):
            subprocess.call(['svn', 'checkout', self.url, self.work_path])


    def export(self, rev_num, dst_path):
        subprocess.call(['svn', 'export', '--force', '-r', rev_num,
                         self.work_path, dst_path])


    def pull(self):
        subprocess.call(['svn', 'update', self.work_path])


    def get_new_revisions(self, from_rev):
        # first update working copy
        self.pull()
        cmd = ['svn','log', '-q', '-r', '%s:HEAD' % from_rev, self.work_path]
        log_proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        out = log_proc.communicate()[0]
        revs = []
        for line in out.splitlines():
            if line[0] != 'r':
                continue
            # r12345 | john | 2009-11-03 00:09:25 +0800 (Tue, 03 Nov 2009)
            revs.append(line.split()[0][1:]) # get first word and remove 'r'
        # exclude old tip/head
        return revs[1:]



class BZR(object):
    def __init__(self, url, work_path):
        self.url = url
        self.work_path = work_path


    def clone(self):
        """SVN checkout"""
	if not os.path.exists(self.work_path):
            subprocess.call(['bzr', 'branch', self.url, self.work_path])


    def export(self, rev_num, dst_path):
        if os.path.exists(dst_path):
            shutil.rmtree(dst_path)
        subprocess.call(['bzr', 'export', '--revision=%s' % rev_num,
                         dst_path, self.work_path])


    def pull(self):
        subprocess.call(['bzr', 'pull', '--directory=%s' % self.work_path])


    def get_new_revisions(self, from_rev):
        # first update working copy
        self.pull()
        cmd = ['bzr', 'log', '--line', '--forward',
               '--revision=%s..'%from_rev, self.work_path]
        log_proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        out = log_proc.communicate()[0]
        revs = []
        for line in out.splitlines():
            # 174: eduardo 2009-10-30 xxx yyy zzz
            revs.append(line.split()[0][:-1]) # get first word and remove ':'
        # exclude old tip/head
        return revs[1:]



def get_vcs(vcs_name, url, work_path):
    """return a VCS object"""
    vcs_map = {'svn': SVN,
               'bzr': BZR}
    return vcs_map[vcs_name](url, work_path)
