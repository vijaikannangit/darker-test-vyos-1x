#!/usr/bin/env python3
#
# Copyright (C) 2019 VyOS maintainers and contributors
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 or later as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os

from sys import exit
from copy import deepcopy
from jinja2 import Template
from subprocess import Popen, PIPE
from time import sleep

from vyos.config import Config
from vyos.ifconfig import Interface
from vyos import ConfigError
from netifaces import interfaces

# Please be careful if you edit the template.
config_pppoe_tmpl = """
### Autogenerated by interfaces-pppoe.py ###

{% if description %}
# {{ description }}
{% endif %}

# Require peer to provide the local IP address if it is not
# specified explicitly in the config file.
noipdefault

# Don't show the password in logfiles:
hide-password

# Standard Link Control Protocol (LCP) parameters:
lcp-echo-interval 20
lcp-echo-failure 3

# RFC 2516, paragraph 7 mandates that the following options MUST NOT be
# requested and MUST be rejected if requested by the peer:
# Address-and-Control-Field-Compression (ACFC)
noaccomp

# Asynchronous-Control-Character-Map (ACCM)
default-asyncmap

# Override any connect script that may have been set in /etc/ppp/options.
connect /bin/true

# Don't try to authenticate the remote node
noauth

# Don't try to proxy ARP for the remote endpoint. User can set proxy
# arp entries up manually if they wish.  More importantly, having
# the "proxyarp" parameter set disables the "defaultroute" option.
noproxyarp

plugin rp-pppoe.so
{{ source_interface }}
persist
ifname {{ intf }}
ipparam {{ intf }}
debug
logfile /var/log/vyatta/ppp_{{ intf }}.log
{% if 'auto' in default_route -%}
defaultroute
{% elif 'force' in default_route -%}
defaultroute
replacedefaultroute
{% endif %}
mtu {{ mtu }}
mru {{ mtu }}
user "{{ auth_username }}"
password "{{ auth_password }}"
{% if name_server -%}
usepeerdns
{% endif %}
{% if ipv6_enable -%}
+ipv6
{% endif %}

"""

default_config_data = {
    'access_concentrator': '',
    'auth_username': '',
    'auth_password': '',
    'on_demand': False,
    'default_route': 'auto',
    'deleted': False,
    'description': '',
    'disable': False,
    'intf': '',
    'idle_timeout': '',
    'ipv6_autoconf': False,
    'ipv6_enable': False,
    'local_address': '',
    'mtu': '1492',
    'name_server': True,
    'remote_address': '',
    'service_name': '',
    'source_interface': ''
}

def subprocess_cmd(command):
    p = Popen(command, stdout=PIPE, shell=True)
    p.communicate()

def get_config():
    pppoe = deepcopy(default_config_data)
    conf = Config()
    base_path = ['interfaces', 'pppoe']

    # determine tagNode instance
    try:
        pppoe['intf'] = os.environ['VYOS_TAGNODE_VALUE']
    except KeyError as E:
        print("Interface not specified")

    # Check if interface has been removed
    if not conf.exists(base_path + [pppoe['intf']]):
        pppoe['deleted'] = True
        return pppoe

    # set new configuration level
    conf.set_level(base_path + [pppoe['intf']])

    # Access concentrator name (only connect to this concentrator)
    if conf.exists(['access-concentrator']):
        pppoe['access_concentrator'] = conf.return_values(['access-concentrator'])

    # Authentication name supplied to PPPoE server
    if conf.exists(['authentication', 'user']):
        pppoe['auth_username'] = conf.return_value(['authentication', 'user'])

    # Password for authenticating local machine to PPPoE server
    if conf.exists(['authentication', 'password']):
        pppoe['auth_password'] = conf.return_value(['authentication', 'password'])

    # Access concentrator name (only connect to this concentrator)
    if conf.exists(['connect-on-demand']):
        pppoe['on_demand'] = True

    # Enable/Disable default route to peer when link comes up
    if conf.exists(['default-route']):
        pppoe['default_route'] = conf.return_value(['default-route'])

    # Retrieve interface description
    if conf.exists(['description']):
        pppoe['description'] = conf.return_value(['description'])

    # Disable this interface
    if conf.exists(['disable']):
        pppoe['disable'] = True

    # Delay before disconnecting idle session (in seconds)
    if conf.exists(['idle-timeout']):
        pppoe['idle_timeout'] = conf.return_value(['idle-timeout'])

    # Enable Stateless Address Autoconfiguration (SLAAC)
    if conf.exists(['ipv6', 'address', 'autoconf']):
        pppoe['ipv6_autoconf'] = True

    # Activate IPv6 support on this connection
    if conf.exists(['ipv6', 'enable']):
        pppoe['ipv6_enable'] = True

    # IPv4 address of local end of PPPoE link
    if conf.exists(['local-address']):
        pppoe['local_address'] = conf.return_value(['local-address'])

    # Physical Interface used for this PPPoE session
    if conf.exists(['source-interface']):
        pppoe['source_interface'] = conf.return_value('source-interface')

    # Maximum Transmission Unit (MTU)
    if conf.exists(['mtu']):
        pppoe['mtu'] = conf.return_value(['mtu'])

    # Do not use DNS servers provided by the peer
    if conf.exists(['no-peer-dns']):
        pppoe['name_server'] = False

    # IPv4 address for remote end of PPPoE session
    if conf.exists(['remote-address']):
        pppoe['remote_address'] = conf.return_value(['remote-address'])

    # Service name, only connect to access concentrators advertising this
    if conf.exists(['service-name']):
        pppoe['service_name'] = conf.return_value(['service-name'])

    return pppoe

def verify(pppoe):
    if pppoe['deleted']:
        # bail out early
        return None

    if not pppoe['source_interface']:
        raise ConfigError('PPPoE source interface is missing')

    return None

def generate(pppoe):
    config_file_pppoe = '/etc/ppp/peers/{}'.format(pppoe['intf'])

    # Always hang-up PPPoE connection prior generating new configuration file
    cmd = 'systemctl stop ppp@{}.service'.format(pppoe['intf'])
    subprocess_cmd(cmd)

    if pppoe['deleted']:
        # Delete PPP configuration files
        if os.path.exists(config_file_pppoe):
            os.unlink(config_file_pppoe)

    else:
        # Create PPP configuration files
        tmpl = Template(config_pppoe_tmpl)
        config_text = tmpl.render(pppoe)
        with open(config_file_pppoe, 'w') as f:
            f.write(config_text)

    return None

def apply(pppoe):
    if pppoe['deleted']:
        # bail out early
        return None

    if not pppoe['disable']:
        # Dial PPPoE connection
        cmd = 'systemctl start ppp@{}.service'.format(pppoe['intf'])
        subprocess_cmd(cmd)

    # better late then sorry ... but we can only set interface alias after
    # pppd has been launched and created the interface
    cnt = 0
    while pppoe['intf'] not in interfaces():
        cnt += 1
        if cnt == 50:
            break

        # sleep 250ms
        sleep(0.250)

    try:
        # we need to catch the exception if the interface is not up due to
        # reason stated above
        Interface(pppoe['intf']).set_alias(pppoe['description'])
    except:
        pass

    return None

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
