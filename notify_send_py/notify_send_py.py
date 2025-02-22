#!/usr/bin/env python3

import argparse
from multiprocessing.connection import Client, Listener

from gi.repository import GLib

from .notify3 import notify3

notify2 = notify3

def clean_up_text(text):
    return text.replace("\\n", "\n").replace("\\t", "\t")


class NotifySendPy:
    def __init__(self, loop=None):
        self.loop = loop or GLib.MainLoop()

    def close(self, n):
        print('closed')
        self.loop.quit()

    def action(self, n, text, maybe_params):
        if maybe_params != None:
            print(text + " " + str (maybe_params))
        else:
            print(text)
        if not self.dontQuitOnAction:
            self.loop.quit()

    def force_expire(self, n):
        n.close()
        self.loop.quit()

    def notify(
        self,
        summary,
        body=None,
        *,
        actions=None,
        app_name=None,
        category=None,
        expirey=None,
        hints=None,
        icon=None,
        replaces_id=None,
        replaces_process=None,
        urgency=None,
        dontQuitOnAction=False,
        force_expire=False,
    ):
        self.dontQuitOnAction = dontQuitOnAction
        summary = clean_up_text(summary)
        body = clean_up_text(body or "")

        notify2.init(app_name or "", 'glib')
        if icon and body:
            n = notify2.Notification(summary, message=body, icon=icon)
        elif icon:
            n = notify2.Notification(summary, icon=icon)
        elif body:
            n = notify2.Notification(summary, message=body)
        else:
            n = notify2.Notification(summary)

        if urgency == "low":
            n.set_urgency(notify2.URGENCY_LOW)
        elif urgency == "normal":
            n.set_urgency(notify2.URGENCY_NORMAL)
        elif urgency == "critical":
            n.set_urgency(notify2.URGENCY_CRITICAL)
        elif urgency is not None:
            print("urgency must be low|normal|critical")
            exit()

        if expirey:
            try:
                n.set_timeout(int(expirey))
            except ValueError:
                print("expire-time must be integer")
                exit()

        if category:
            n.set_category(category)

        if hints:
            for hint in hints:
                try:
                    hintparts = hint.split(':')
                    hint_type = hintparts[0]
                    key = hintparts[1]
                    value = ':'.join(hintparts[2:])

                    if hint_type == "boolean":
                        if (value == "True") or (value == "true"):
                            n.set_hint(key, True)
                        else:
                            if (value == "False") or (value == "false"):
                                n.set_hint(key, False)
                            else:
                                print("valid types for boolean are: True|true|False|false")
                                exit()
                    if hint_type == "int":
                        n.set_hint(key, int(value))
                    if hint_type == "string":
                        n.set_hint(key, value)
                    if hint_type == "byte":
                        n.set_hint_byte(key, int(value))
                except ValueError:
                    print("hint has to be in the format TYPE:KEY:VALUE")
                    exit()

        if replaces_id is not None:
            try:
                n.id = int(replaces_id)
            except ValueError:
                print("replaces-id has to be an integer")
                exit()

        if actions:
            n.connect("closed", self.close)
            for action in actions:
                [key, value] = action.split(':', maxsplit=1)
                n.add_action(key, value, self.action)

        if replaces_process:
            # address = ('localhost', 6000)
            try:
                with open('/tmp/notify-send.py.address', 'rb') as pidf:
                    address = pidf.read()
                    try:
                        conn = Client(address)
                    except ValueError:
                        conn = Client(address.decode('utf8'))
                    conn.send([n, replaces_process])
                    conn.close()
            except Exception:
                listener = Listener()
                with open('/tmp/notify-send.py.address', 'wb') as pidf:
                    try:
                        pidf.write(listener.address)
                    except TypeError:
                        pidf.write(listener.address.encode('utf8'))
                replaces_processes = {}
                n.show()
                replaces_processes[replaces_process] = n.id
                # stuff
                while True:
                    conn = listener.accept()
                    [n, replaces_process] = conn.recv()
                    if replaces_process in replaces_processes:
                        n.id = replaces_processes[replaces_process]
                    n.show()
                    replaces_processes[replaces_process] = n.id
                    conn.close()
        else:
            n.show()
            if force_expire:
                GLib.timeout_add(1000 * int(expirey), self.force_expire, n)
            if actions or force_expire:
                self.loop.run()
            return n.id


class NotifySendPyCLI:
    def __init__(self):
        parser = argparse.ArgumentParser()
        parser.add_argument(
            '-u', '--urgency', metavar='LEVEL',
            help='Specifies the urgency level (low, normal, critical).')
        parser.add_argument(
            '-t', '--expire-time', metavar='TIME',
            help=('Specifies the timeout in milliseconds at which'
                  ' to expire the notification.'))
        parser.add_argument(
            '--force-expire', action='store_true',
            help=('Forces --expire-time for non-cooperating daemons by waiting for the specified duration'
                  ' and explicitly closing the notification.'))
        parser.add_argument(
            '-a', '--app-name', metavar='APP_NAME',
            help='Specifies the app name for the icon')
        parser.add_argument(
            '-i', '--icon', metavar='ICON[,ICON...]',
            help='Specifies an icon filename or stock icon to display.')
        parser.add_argument(
            '-c', '--category', metavar='TYPE[,TYPE...]',
            help='Specifies the notification category.')
        parser.add_argument(
            '--hint', metavar='TYPE:NAME:VALUE', nargs='*',
            help=('Specifies basic extra data to pass. Valid types'
                  ' are int, double, string, boolean and byte.'))
        parser.add_argument(
            '-r', '--replaces-id', metavar='ID',
            help='Specifies the id of the notification that should be replaced.')
        parser.add_argument(
            '--replaces-process', metavar='NAME',
            help=('Specifies the name of a notification.'
                  ' Every notification that gets created with the same NAME will'
                  ' replace every notification before it with the same NAME.'))
        parser.add_argument(
            '--action', metavar='KEY:NAME', nargs='*',
            help=('Specifies actions for the notification. The action with the key'
                  ' "default" will be dispatched on click of the notification.'
                  ' Key is the return value, name is the display-name on the button.'))
        parser.add_argument(
            '--dontQuitOnAction', action='store_true',
            help=('Keeps running until the notification has been closed, instead'
                  ' of stopping after the first action was received.'))
        parser.add_argument(
            'SUMMARY',
            help=('Summary of the notification. Usage of \\n and \\t is possible.'))
        parser.add_argument(
            'BODY', nargs='?',
            help=('Body of the notification. Usage of \\n and \\t is possible.'))
        args = parser.parse_args()
        n_id = NotifySendPy().notify(
            summary=args.SUMMARY,
            body=args.BODY,
            actions=args.action,
            app_name=args.app_name,
            category=args.category,
            expirey=args.expire_time,
            force_expire=args.force_expire,
            hints=args.hint,
            icon=args.icon,
            replaces_id=args.replaces_id,
            replaces_process=args.replaces_process,
            urgency=args.urgency,
            dontQuitOnAction=args.dontQuitOnAction
        )
        if n_id is not None:
            print(n_id)


def main():
    NotifySendPyCLI()


if __name__ == '__main__':
    main()
