#!/usr/bin/python

""" Bro profiler controller """

import subprocess
import time


class system_config:

    """Boiler plate code for interacting with the system
    Class variables-

        node_cfg: the lcoation of the node.cfg to be modified by bro_device : /usr/local/bro/etc/node.cfg
        load_bro: the location of the load.bro file where we add scripts :  /misc/XXXX
    """

    def __init__(self, node_cfg, load_bro):
        self.node_cfg = node_cfg
        self.load_bro = load_bro

    def modify_node_config(self, bro_device):
        """ Modify the node config with bro_device information """
        with open(self.node_cfg, 'a') as node_cfg_file:
            node_cfg_file.write(bro_device.config_format())

    def modify_local_file(self, bro_script):
        """Modifies the local.bro script with the location of the new script on manager. Use broctl_refresh to get nodes to use it"""
        with open(self.load_bro, 'a') as local_bro_file:
            # store scripts to be loaded in brofiler directory on the manager.
            local_string = "\n###Brofiler###\n@load brofiler/{0}".format(
                bro_script)
            local_bro_file.write(local_string)


class bro_device:

    """ Used to define the type of bro device we are going to be spinning up. We can create either mangers, proxies, or workers. Only workers require interface information
    Class variables-
        Ï
        name: the name of the device
        role: can either be manger, worker, host, standalone (standalone should only be used for local testing purposes)
        host: the host address
        interface: the interface for bro to observe
    """

    def __init__(self, name, role, host, interface='null'):
        self.name = name
        self.role = role
        self.host = host
        self.interface = interface

    def config_format(self):

        if self.role != ('worker' or 'standalone'):
            return "#\n###OTHER###\n[{0}]\ntype={1}\nhost={2}\n".format(
                self.name,
                self.role,
                self.host)

        else:
            return "#\n###WORKER###\n[{0}]\ntype={1}\nhost={2}\ninterface={3}".format(
                self.name,
                self.role,
                self.host,
                self.interface)


class netstat:

    """Output of each device reutrned by 'broctl netstats':

    bro: 1423861198.685558 recvd=25118568 dropped=69563523 link=94682096

    Contains information about the following-

        device : what is the name of the device, defined in node.cfg
        time: the time that the measurment was taken, in Unix epoc time
        recvd: this is the number of packets that have been successfully analyzed
        dropped: these are packets that are dropped due to lack of resources
        link: these are the total number of packets that have been recieved, regardless of whether they have been analyzed
    """

    def __init__(self, device, time, recvd, dropped, link):
        self.device = device
        self.time = time
        self.recvd = float(recvd)
        self.dropped = float(dropped)
        self.link = float(link)

    def confirm(self):
        """ Sanity check if the number of dropped and recvd matches number of packets on the link """
        if (self.recvd + self.dropped != self.link):
            return False
        else:
            return True

    def loss_rate(self):
        """ Loss rate percentage is determiend by dropped divided by total on link"""
        return self.dropped / self.link

    def success_rate(self):
        """ Success rate percentage is determiend by success divided by total on link"""
        if self.link != 0:
            return self.recvd / self.link
        else:
            return 1

    def print_all(self):
        """ Prints all of the useful information conatined in this object, useful for debugging purposes"""
        print('NETSTAT')
        print("Device: {}".format(self.device))
        print("Time: {}".format(self.time))
        print("Recvd: {}".format(self.recvd))
        print("Dropped: {}".format(self.dropped))
        print("Link: {}".format(self.link))
        print('======')


class capstat:

    """Output of link information returned by 'broctl snapshots', based on a 10s average:

    localhost/eth2        36.3       25.6

    Contains information about the following-

        host/interface : the interface of the device being meauserd (TODO - possibly split these into two other object variables)
        kpps : 10s avg of number of kpps on the link
        mbps : 10s avg of speed rate on the link

    """

    def __init__(self, interface, kpps, mbps):
        self.interface = interface
        self.kpps = kpps
        self.mbps = mbps

    """ Prints all of the useful information conatined in this object, useful for debugging purposes"""

    def print_all(self):
        print('CAPSTAT')
        print("Interface: {}".format(self.interface))
        print("kpps: {}".format(self.kpps))
        print("mbps: {}".format(self.mbps))
        print('------')


def collect_netstats():
    """ This function reutrns an array of netstat objects for each bro device returned by 'broctl netstats'.

    [BroControl] > netstats
            bro: 1423861198.685558 recvd=25118568 dropped=69563523 link=94682096
            shmo: 1423861198.685558 recvd=500 dropped=1337 link=1837

    This would create two netstat objects, bro and shmo, put them into an array based on the time, the netstats_snapshot, and return the array
    """
    netstats_snapshot = []

    try:
        netstats_string = subprocess.check_output(
            'sudo /usr/local/bro/bin/broctl netstats',
            shell=True)
        # split on the new lines for each of the devices
        netstats_split_line = netstats_string.splitlines()

        for i in range(0, len(netstats_split_line)):
            # remove the unwanted characters
            netstats_split = netstats_string.strip().replace(
                ':',
                '').replace(
                'recvd=',
                '').replace(
                'dropped=',
                '').replace(
                'link=',
                '').split()
            # instantiate the object and add it to the array to be returned
            netstats_snapshot.append(
                netstat(
                    netstats_split[0],
                    netstats_split[1],
                    netstats_split[2],
                    netstats_split[3],
                    netstats_split[4]))
        return netstats_snapshot

    except subprocess.CalledProcessError:
        print('FAILED netstats')


def collect_capstats():
    """This function returns an array of capstat object for each interface returned by 'broctl capstats'

    [BroControl] > capstats

    Interface             kpps       mbps       (10s average)
    ----------------------------------------
    localhost/eth2        36.3       25.6

    This would create a single netstat object, put it into the array capstats_snapshot, and return it.
    """

    capstats_snapshot = []
    # NOTE: capstats seems to output on the stderror FD NOT stdout
    capstats_string = subprocess.check_output(
        'sudo /usr/local/bro/bin/broctl capstats',
        stderr=subprocess.STDOUT,
        shell=True)
    # split capstats into multiple lines
    capstats_split_line = capstats_string.splitlines()

    # go through the lines for the different interfaces, starting on the third
    # (first two are useless)
    for i in range(3, len(capstats_split_line)):
        # split on the words
        capstats_split_word = capstats_split_line[i].split()

        if (len(capstats_split_word) is 0):
            return

        # instatiate a capstats_snapshot for each of the interfaces and add it
        # to our capstats_snapshot list
        capstats_snapshot.append(
            capstat(
                capstats_split_word[0],
                capstats_split_word[1],
                capstats_split_word[2]))

    return capstats_snapshot


def analyze_netstats(netstat_snapshots):
    """This takes in an array of netstat snapshots, each of which contain information about multiple devices. It looks at the first snapshot in the array
    and calculates the avg success and failure based on this.

    Returns a useless boolean for now, change to important data in the future.
    """

    total_success = 0

    for netstat_snapshot in netstat_snapshots:
        # look at the succes rate for the first device for each
        # snapshot,net_snapshot[0], and use it to calculate the avg
        total_success += netstat_snapshot[0].success_rate()

    # calculate avg based on total number of snapshots
    avg_success = (total_success / len(netstat_snapshots))

    print("Avg success: {}".format(avg_success))
    print("Avg failure: {}".format(1 - avg_success))
    print('=====')

    # TODO: return useful data in the future
    return True


def broctl_install():
    subprocess.check_output(
        'sudo /usr/local/bro/bin/broctl install',
        shell=True)


def broctl_restart():
    subprocess.check_output(
        'sudo /usr/local/bro/bin/broctl restart',
        shell=True)


def broctl_refresh():
    broctl_install()
    broctl_restart()


def main():

    starttime = time.time()

    broctl_refresh()

    # this is a collection of snapshots collected every cycle
    netstat_snapshots = []
    capstat_snapshots = []

    test_config = system_config(
        '/usr/local/bro/etc/node.cfg',
        '/home/user/local.bro')
    test_device = bro_device('TEST', 'worker', '1.1.1.1', 'eth0')

    # test_config.modify_local_file('TEST_SCRIPT')
    # test_config.modify_node_config(test_device)

    # this collects a snapshot every x seconds
    for i in range(0, 100):

        netstat_snapshot = collect_netstats()
        netstat_snapshots.append(netstat_snapshot)
        netstat_snapshot[0].print_all()


#        capstat_snapshot = collect_capstats()
#        capstat_snapshots.append(capstat_snapshot)
#        capstat_snapshot[0].print_all()
        i += 1
        analyze_netstats(netstat_snapshots)
        time.sleep(5.0 - ((time.time() - starttime) % 5.0))

if __name__ == "__main__":
    main()
