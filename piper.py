from __future__ import print_function
import sys
import six
from gevent import socket
from gevent.queue import Queue
from gevent.socket import wait_read
import gevent

def parse_arg(arg):
    (proto, role, port) = arg.split(':')
    if proto != 'tcp' and proto != 'udp':
        print('Expected one of tcp or udp', file=sys.stderr)
        sys.exit(1)
    if role != 'client' and role != 'server':
        print('Expected one of client or server', file=sys.stderr)
        sys.exit(1)
    return (proto, role, int(port))

args = sys.argv[1:]
print('piping over', parse_arg(args[0]))

def udp_client(idx, port, queue):
    address = ('127.0.0.1', port)
    sock = socket.socket(type=socket.SOCK_DGRAM)
    sock.connect(address)
    while True:
        try:
            wait_read(sock.fileno())
            data, address = sock.recvfrom(8192)
            print('%s:%s: got %r' % (address + (data, )))
            queue.put((idx, data, address))
        except socket.error as e:
            print('Socket error:', e)
            break

def udp_server(idx, port):
    address = ('127.0.0.1', port)
    sock = socket.socket(type=socket.SOCK_DGRAM)
    sock.bind(address)

    def read():
        while True:
            try:
                wait_read(sock.fileno())
                data, address = sock.recvfrom(port)
                print('%s:%s: got %r' % (address + (data, )))
                out_queue.put((data, address))
            except socket.error as e:
                print('Socket error:', e)
                break

    def write():
        while True:
            try:
                wait_write(sock.fileno())
                msg = in_queue.get()
                data, address = sock.send(msg, ('127.0.0.1', port))
                print('%s:%s: got %r' % (address + (data, )))
                queue.put((data, address))
            except socket.error as e:
                print('Socket error:', e)
                break

    gevent.spawn(read)
    gevent.spawn(write)

def udp(idx, type, port, queue):
    if type == 'client':
        return udp_client(idx, port, queue)
    else:
        return udp_server(idx, port, queue)

queue_in = Queue()
udp(0, parse_arg(args[0])[1], parse_arg(args[0])[2], queue)
gevent.wait()
