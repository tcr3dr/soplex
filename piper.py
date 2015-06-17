#!/usr/bin/env python

# e.g.
# python piper.py tcp:server:5000 udp:in:5500 udp:out:5511
# python piper.py tcp:client:5000 udp:out:5555 udp:in:5512

from __future__ import print_function
import sys
import six
from gevent import socket
from gevent.queue import Queue
from gevent.socket import wait_read, wait_write
import gevent
import base64
import json

def parse_arg(arg):
    (proto, role, port) = arg.split(':')
    if proto != 'tcp' and proto != 'udp':
        print('Expected one of tcp or udp', file=sys.stderr)
        sys.exit(1)
    if role != 'in' and role != 'out' and role != 'server' and role != 'client':
        print('Expected one of in or out', file=sys.stderr)
        sys.exit(1)
    return (proto, role, int(port))

def udp(idx, role, port):
    global ports

    address = ('127.0.0.1', port)
    sock = socket.socket(type=socket.SOCK_DGRAM)

    if role == 'in':
        sock.bind(address)

    in_queue = Queue()
    out_queue = Queue() 

    def read():
        while True:
            try:
                wait_read(sock.fileno())
                data, address = sock.recvfrom(port)
                print(role, 'received %s:%s: got %r' % (address + (data, )))
                in_queue.put((data, address))
            except socket.error as e:
                print('Socket error:', e)
                break

    def write():
        while True:
            try:
                wait_write(sock.fileno())
                msg = out_queue.get()
                print(role, 'sending %s' % msg)
                out_bytes = sock.sendto(msg, address)
            except socket.error as e:
                print('Socket error:', e)
                break

    def resident():
        buf = ''
        while True:
            pair = in_queue.get()
            if idx == 0:
                buf += pair[0]
                res = buf.split('\n')
                buf = res.pop()
                for item in res:
                    (tidx, b) = json.loads(item)
                    msg = base64.b64decode(b)
                    ports[tidx][1].put(msg)
            else:
                ports[0][1].put(json.dumps([idx, base64.b64encode(pair[0])]) + '\n')


    if role == 'in':
        gevent.spawn(read)
    if role == 'out':
        gevent.spawn(write)
    gevent.spawn(resident)

    return (in_queue, out_queue)


def tcp(idx, role, port):
    global ports

    address = ('127.0.0.1', port)

    in_queue = Queue()
    out_queue = Queue()

    conns = []

    def connectify():
        sock = socket.socket(type=socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        if role == 'server':
            sock.bind(address)
            sock.listen(1)
        else:
            print(address)
            while True:
                try:
                    sock.connect(address)
                    break
                except socket.error as e:
                    sock = socket.socket(type=socket.SOCK_STREAM)
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    if e.errno == 61:
                        print('Waiting for server...')
                        gevent.sleep(1)
                    else:
                        raise e

        if role == 'client':
            gevent.spawn(read, sock)
            gevent.spawn(write, sock)
        if role == 'server':
            gevent.spawn(read_clients, sock)
            gevent.spawn(write_clients, conns)
        gevent.spawn(resident)


    def read_clients(sock):
        while True:
            try:
                wait_read(sock.fileno())
                conn, addr = sock.accept()
                conns.append(conn)
                gevent.spawn(read, conn)
            except socket.error as e:
                print('Socket error:', e)
                break

    def read(conn):
        while True:
            try:
                wait_read(conn.fileno())
                data = conn.recv(port)
                print(role, 'received %r' % (data, ))
                if not data:
                    break
                in_queue.put(data)
            except socket.error as e:
                print('Socket error:', e)
                break
        conn.close()
        try:
            conns.remove(conn)
        except:
            pass

    def write(sock):
        while True:
            try:
                wait_write(sock.fileno())
                msg = out_queue.get()
                print(role, 'sending %s' % msg)
                out_bytes = sock.send(msg)
            except socket.error as e:
                print('Socket error:', e)
                break

    def write_clients(conns):
        while True:
            try:
                # wait_write(sock.fileno())
                msg = out_queue.get()
                print(role, 'sending %s' % msg)
                for conn in conns:
                    out_bytes = conn.send(msg)
            except socket.error as e:
                print('Socket error:', e)
                break

    def resident():
        buf = ''
        while True:
            pair = in_queue.get()
            if idx == 0:
                buf += pair
                res = buf.split('\n')
                buf = res.pop()
                for item in res:
                    (tidx, b) = json.loads(item)
                    msg = base64.b64decode(b)
                    ports[tidx][1].put(msg)
            else:
                ports[0][1].put(json.dumps([idx, base64.b64encode(pair)]) + '\n')


    gevent.spawn(connectify)

    return (in_queue, out_queue)


args = sys.argv[1:]

ports = []

for arg in args:
    (proto, role, port) = parse_arg(arg)
    if len(ports) == 0:
        print('piping over', parse_arg(arg))
    else:
        print('attached to', parse_arg(arg))
    ports.append((tcp if proto == 'tcp' else udp)(len(ports), role, port))

gevent.wait()
