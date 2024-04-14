#!/usr/bin/env python

import os
import sys
import platform
import glob
import subprocess
import smtplib
import re
from tkinter import Tk, Text
from configparser import SafeConfigParser
from string import printable


class StealthRelayError(Exception):
    pass


class ConfigError(StealthRelayError):
    pass


def get_home_dir():
    return os.path.expanduser('~') if sys.platform != 'win32' else os.environ.get('USERPROFILE', 'C:\\')


def read_config(config_file):
    cp = SafeConfigParser()
    cp.read(config_file)
    return dict(cp.items('asection'))


def get_profiles(home):
    profiles = None
    if sys.platform == "darwin":
        profiles = os.path.join(home, "Library", "Thunderbird", "Profiles")
    elif sys.platform.startswith("linux"):
        profiles = os.path.join(home, ".thunderbird")
    elif sys.platform == "win32":
        v = int(platform.version().split('.', 1)[0])
        profiles = os.path.join(home, "Application Data", "Thunderbird", "Profiles") if v in (4, 5) \
            else os.path.join(home, "AppData", "Roaming", "Thunderbird", "Profiles")
    return profiles


def main():
    home = get_home_dir()
    config_file = os.path.join(home, ".stealthrelay")
    if not os.path.exists(config_file):
        raise ConfigError("Unable to find '%s' config." % config_file)
    config = read_config(config_file)
    profiles = config.get('mail') or get_profiles(home)
    if profiles is None:
        raise ConfigError("Unable to find Thunderbird profile.")
    debug = config.get("debug", False)
    if debug:
        tk = Tk()
        tk.title("StealthRelay")
        txt = Text(tk)
        txt.pack(expand=True, fill='both')
    stealthcoind = config['daemon']
    pattern = os.path.join(profiles, "*.default")
    default = glob.glob(pattern)[0]
    stealthtext = os.path.join(default, "Mail", "Local Folders", "StealthRelay")
    client_id = config['client_id']
    rgx = '(%s,[A-Za-z0-9+/]+=*)(?:[^A-Za-z0-9+/=]|$)' % client_id
    clientRE = re.compile(rgx)
    lines = open(stealthtext).read().splitlines()[::-1]
    subject = []
    for line in lines:
        line = "".join([c for c in line if c in printable])
        line = line.replace(" ", "+")
        line = line.split()
        line = "".join(line)
        subject.append(line.strip())
        if client_id in line:
            break
    subject = "".join(subject[::-1])
    m = clientRE.search(subject)
    if m is None:
        if debug:
            txt.insert('end', "Could not find StealthText message.\n")
        msg = "<<Parse Error>>"
        raise SystemExit
    else:
        msg = m.group(1)
        if debug:
            txt.insert('end', msg)
    command = [stealthcoind, "decryptsend", "%s" % (msg,)]
    output = subprocess.check_output(command)
    if debug:
        txt.insert('end', "\n\n" + output.strip())
    sys.stderr.write(output)
    if "confirm_address" in config:
        if output.startswith('<<'):
            message = config.get("fail", "-") + "\n"
        else:
            message = config.get("success", "+") + "\n"
        sender = config.get("sender")
        receivers = [config['confirm_address']]
        try:
            server = smtplib.SMTP(config['server'])
            server.starttls()
            server.login(config['username'], config['password'])
            server.sendmail(sender, receivers, message)
            if debug:
                txt.insert('end', "\n\n" + "Email sent successfully.")
            else:
                sys.stderr.write("Email sent successfully.\n")
        except smtplib.SMTPException:
            if debug:
                txt.insert('end', "\n\n" + "Email unsuccessful.")
            else:
                sys.stderr.write("Email unsuccessful.\n")
    if debug:
        tk.mainloop()


if __name__ == "__main__":
    main()
