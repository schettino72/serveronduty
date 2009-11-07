"""Interface to VCS with some basic operations

Operations:

-get_new_revisions: return the description information of
revisions newer than the working copy
@return: a dictionary or relevant values like:
{ 'revision': '174'
  'committer': 'somebody'
  'comment': 'commit message'} 

"""

import os
import shutil
import subprocess

#TODO: it would not be a bad idea to describe the SCM interface we would like to support



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
            revs.append(
                { 'revision': line.split()[0][1:]}) # get first word and remove 'r'
        # exclude old tip/head
        return revs[1:]



class BZR(object):
    def __init__(self, url, work_path):
        self.url = url
        self.work_path = work_path


    def clone(self):
        """SVN checkout"""
        print "bzr cloning, ", self.url, self.work_path
        if not os.path.exists(self.work_path):
            subprocess.call(['bzr', 'branch', self.url, self.work_path])


    def export(self, rev_num, dst_path):
        print "bzr exporting..."
        if os.path.exists(dst_path):
            shutil.rmtree(dst_path)
        subprocess.call(['bzr', 'export', '--revision=%s' % rev_num,
                         dst_path, self.work_path])


    def pull(self):
        print "bzr pulling..."
        subprocess.call(['bzr', 'pull', '--directory=%s' % self.work_path])


    def get_new_revisions(self, from_rev):
        # first update working copy
        self.pull()
        print "getting log"
        cmd = ['bzr', 'log', '--line', '--forward',
               '--revision=%s..'%from_rev, self.work_path]
        print cmd
        log_proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        out = log_proc.communicate()[0]
        print "bzr log, =>\n", out
        revs = []
        for line in out.splitlines():
            #TODO: bzr log --line show only the top line of commit message, maybe the whole logic should be reconsidered a little
            #with maxsplit, top line comment will be the value of the last element
            line_split = line.split(" ", 3)
            
            # 174: eduardo 2009-10-30 xxx yyy zzz
            revs.append(
                { 'revision': line_split[0][:-1], # get first word and remove ':'
                  'committer':  line_split[1],
                  'comment': line_split[3]
                })
                        
        # exclude old tip/head
        return revs[1:]


class HG(object):
    def __init__(self, url, work_path):
        self.url = url
        self.work_path = work_path


    def clone(self):
        """hg clone"""
        if not os.path.exists(self.work_path):
            subprocess.call(['hg', 'clone', self.url, self.work_path])


    def export(self, rev_num, dst_path):
        if os.path.exists(dst_path):
            shutil.rmtree(dst_path)
        cmd = ['hg', 'archive', '-R', self.work_path,
                                '-r', rev_num, dst_path]
        subprocess.call(cmd)

    def pull(self):
        subprocess.call(['hg', 'pull', '-R', self.work_path, self.url])


    def get_new_revisions(self, from_rev):
        # first update working copy
        self.pull()
        cmd = ['hg', 'log',
                            '-r', '%s:tip' % from_rev,
                            '-R', self.work_path]
        log_proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        out = log_proc.communicate()[0]
        revs = []
        for line in out.splitlines():
            if line.startswith('changeset'):
                # changset:  10:bafsafasdfa 
                revs.append(
                    { 'revision': line.split()[1].split(':')[0]})
        # exclude old tip/head
        return revs[1:]


def get_vcs(vcs_name, url, work_path):
    """return a VCS object"""
    vcs_map = {'svn': SVN,
               'bzr': BZR,
               'hg': HG}
    return vcs_map[vcs_name](url, work_path)
