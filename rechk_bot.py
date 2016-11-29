import argparse
import json
import logging
import os
import subprocess
import sys


def gerrit_cmd(gerrit_c):
    #TODO(dukov) Replase this with paramiko
    ssh_cmd = "ssh -p 29418 dukov@review.openstack.org"
    cmd = ssh_cmd.split() + [gerrit_c]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    p.wait()
    return p.stdout.readlines()


def get_commit_info(crid):
    gerrit_q = "gerrit query --format=JSON --current-patch-set %s" % crid
    logging.debug("Executing cmd %s" % gerrit_q)
    raw_data = gerrit_cmd(gerrit_q)[0]
    logging.debug("Loaded raw-data %s" % raw_data)
    return json.loads(raw_data)


def get_commit_status(commit_info):
    logging.info("Getting status for %s" % commit_info['number'])
    approvals = commit_info['currentPatchSet']['approvals']
    logging.debug("Got approvals %s" % approvals)

    for approval in approvals:
        if approval['by']['username'] == 'fuel-ci' and approval['value'] == '-1':
            logging.info("Commit %s needs to be retriggered" % commit_info['number'])
            return True

    logging.info("Commit %s does not need to be retriggered" % commit_info['number'])
    return False


def retrigger_commit(commit_info):
    logging.info("Retrigger commit %s" % commit_info['number'])
    gerrit_review = "gerrit review -m 'fuel: recheck' %s,%s" %(commit_info['number'], commit_info['currentPatchSet']['number'])
    logging.debug("Executing cmd %s" % gerrit_review)
    res = gerrit_cmd(gerrit_review)
    return res


def get_crs_by_topic(topic):
    logging.info("Gerring commit list for topic %s" % topic)
    res = []
    gerrit_q = "gerrit query --format=JSON --current-patch-set topic:%s status:open" % topic 
    raw_data = gerrit_cmd(gerrit_q)[:-1]
    logging.debug("Loaded raw-data %s" % raw_data)

    for line in raw_data:
        res.append(json.loads(line)['number'])
    logging.info("Got list of CRs %s for topic %s" % (res, topic))
    return res


if __name__ == '__main__':
    bot_dir = os.path.dirname(os.path.abspath(__file__))
    log_file = os.path.join(bot_dir, 'bot.log')
    log_level = logging.INFO

    parser = argparse.ArgumentParser(description='OpenStack Gerrit Bot')
    parser.add_argument('-c',
                        '--commits',
                        dest='commit',
                        nargs='+',
                        help='List of commits to ckeck'
    )


    parser.add_argument('-t',
                        '--topic',
                        dest='topic',
                        help='Topic to check'
    )

    parser.add_argument('-d',
                        '--dubug',
                        dest='debug',
                        action='store_true',
                        help='Enable debug'
    )
    args = parser.parse_args()


    if args.debug:
        log_level = logging.DEBUG

    logging.basicConfig(filename=log_file, level=log_level, format='%(asctime)s %(levelname)s %(message)s')

    commit_list = []
    if args.topic:
        commit_list += get_crs_by_topic(args.topic)

    if args.commit:
        commit_list += args.commit

    for cr in commit_list:
        commit = get_commit_info(cr)
        needs_retrigger = get_commit_status(commit)
        if needs_retrigger:
            retrigger_commit(commit)
