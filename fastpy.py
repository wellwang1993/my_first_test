#!/usr/bin/python
#-*- coding:utf-8 -*-

import socket, logging
import logging.handlers  
import logging.config  
import select, errno
import os
import sys
import traceback
import gzip
from StringIO import StringIO
import Queue
import threading
import time
import thread
import cgi
from cgi import parse_qs
import json
import imp
from os.path import join, getsize
from multiprocessing import cpu_count
from urllib import unquote
import re
try:
    import gevent
    import gevent.monkey
    gevent.monkey.patch_socket()
    Install_gevent = True
except Exception, e:
    Install_gevent = False

##################user config ##################
logging.config.fileConfig('logging.conf')
logger = logging.getLogger("main")
static_file_dir = "static"
thread_num = 2*cpu_count()
MaxReadSize = 1024*1024*1024
#############################################

static_dir = "/%s/" % static_file_dir
read_cache_dir = "read_cache"
cache_static_dir = "cache_%s" % static_file_dir
#if not os.path.exists(cache_static_dir):
#    os.makedirs(cache_static_dir)
#if not os.path.exists(read_cache_dir):
#    os.makedirs(read_cache_dir)
gzipdic = {"HTM":"text/html",
        "HTML":"text/html",
        "CSS":"text/css",
        "JS":"text/javascript",
        "TXT":"text/plain",
        "XML":"text/xml"}

mimedic = {"HTM":"text/html",
        "HTML":"text/html",
        "CSS":"text/css",
        "JS":"text/javascript",
        "TXT":"text/plain",
        "XML":"text/xml",
        "APK":"application/vnd.android.package-archive",
        "PXL":"application/iphone",
        "IPA":"application/iphone",
        "LUA":"application/force-download"}

def getTraceStackMsg():
    tb = sys.exc_info()[2]
    msg = ''
    for i in traceback.format_tb(tb):
        msg += i
    return msg

#action_dic = {}
action_time = {}
listfile = os.listdir("./")
for l in listfile:
    if l == str(__file__):
        continue
    prefixname, extname = os.path.splitext(l)
    if extname == ".py":
        try:
            __import__(prefixname)
        except Exception, e:
            print str(e)+getTraceStackMsg()
            continue
        mtime = os.path.getmtime(l)
        action_time[prefixname] = mtime
        #action_dic[prefixname] = action

def CoroutineResume(work,param,epoll_fd,fd):
    work.process(param,epoll_fd,fd)
    
#class FeimatLog():
#    def __init__(self, filename):
#        logtime = time.strftime(".%Y-%m-%d")
#        self.curlogname = filename + logtime
#        self.f = open(self.curlogname, "a")
#        self.basename = filename
#
#    def __del__(self):
#        self.f.close()
#
#    def log(self, msg):
#        curlogtime = time.strftime(".%Y-%m-%d")
#        detaillogtime = time.strftime("[%Y-%m-%d %H:%M:%S] ")
#        curlogname = self.basename + curlogtime
#        if curlogname != self.curlogname:
#            self.f.close()
#            self.curlogname = curlogname
#            self.f = open(self.curlogname, "a")
#        self.f.write(detaillogtime + msg+"\n")
#        self.f.flush()
#        pass
#
def myparse_qs(input, d):
    p_list = input.split("&")
    for sub in p_list:
        if sub == None or sub == "" or \
                "=" not in sub:
            continue
        v_list = sub.split("=")
        k = unquote(v_list[0])
        v = unquote(v_list[1])
        d[str(k)] = str(v)

class QuickHTTPRequest():
    def __init__(self, res_headers,data,epoll_fd,fd):
        self.res_headers = res_headers
        self.data = data
        self.epoll_fd = epoll_fd
        self.fd = fd

    def dec2hex(self,dec_num):
        hex_num = hex(dec_num)
        return hex_num[2:]

    def printChunk(self,res):
        add_head = ""
        try:
            dec_len = len(res)
            self.data["keepalive"] = True
            res_len = self.dec2hex(len(res))
            if "printChunk" in self.data:
                if dec_len > 0:
                    write_data = self.data.get("writedata", "")
                    write_data += "%s\r\n%s\r\n" % (res_len, res)
                    self.data["writedata"] = write_data
            else:
                self.res_headers["Transfer-Encoding"] = "chunked"
                for key in self.res_headers:
                    add_head += "%s: %s\r\n" % (key, self.res_headers[key])
                self.data["printChunk"] = True #set start print chunk
                write_data = self.data.get("writedata", "")
                if dec_len > 0:
                    write_data += "HTTP/1.1 200 OK\r\n%s\r\n%s\r\n%s\r\n" % (add_head, res_len, res)
                else:
                    write_data += "HTTP/1.1 200 OK\r\n%s\r\n" % (add_head)
                self.data["writedata"] = write_data
                if "read_cache_name" in self.data:
                    os.remove(self.data["read_cache_name"])
                    del self.data["read_cache_name"]
            self.epoll_fd.modify(self.fd, select.EPOLLOUT | select.EPOLLIN | select.EPOLLERR | select.EPOLLHUP)
        except Exception, e:
            print str(e)+getTraceStackMsg()
        
    def flushChunk(self):
        try:
            if "printChunk" in self.data:
                write_data = self.data.get("writedata", "")
                write_data += "0\r\n\r\n"
                self.data["writedata"] = write_data
                del self.data["printChunk"] #set stop print chunk
                self.epoll_fd.modify(self.fd, select.EPOLLOUT | select.EPOLLIN | select.EPOLLERR | select.EPOLLHUP)
        except Exception, e:
            print str(e)+getTraceStackMsg()

    def ret(self,code,res):
        add_head = ""
        try:
            if res == None:
                return None
            if self.res_headers.get("Content-Encoding","") == "gzip":
                buf = StringIO()
                f = gzip.GzipFile(mode='wb', fileobj=buf)
                f.write(res)
                f.close()
                res = buf.getvalue()
            logger.info(" success: %s" % (self.path))
        except Exception, e:
            print str(e)+getTraceStackMsg()
            logger.error(" fail: %s %s" % (self.path, str(e)+getTraceStackMsg()))
            res = "404 Not Found"
        try:
            if self.res_headers.get("Connection","") == "close":
                self.data["keepalive"] = False
            res_len = len(res)
            self.res_headers["Content-Length"] = res_len
            for key in self.res_headers:
                add_head += "%s: %s\r\n" % (key, self.res_headers[key])
            if res == "404 Not Found":
                self.data["writedata"] = "HTTP/1.1 404 Not Found\r\n%s\r\n%s" % (add_head, res)
            elif code != 200:
                self.data["writedata"] = "HTTP/1.1 %s error\r\n%s\r\n%s" % (code, add_head, res)
            else:
                self.data["writedata"] = "HTTP/1.1 200 OK\r\n%s\r\n%s" % (add_head, res)
            if "read_cache_name" in self.data:
                os.remove(self.data["read_cache_name"])
                del self.data["read_cache_name"]
            self.epoll_fd.modify(self.fd, select.EPOLLOUT | select.EPOLLIN | select.EPOLLERR | select.EPOLLHUP)
        except Exception, e:
            print str(e)+getTraceStackMsg()

    def parse(self, param):
        self.client_ip = param["addr"][0]
        self.client_port = param["addr"][1]
        if "rc" in param:
            fp = param["rc"]
            data = ""
            while True:
                subdata = fp.read(1024)
                if subdata == "":
                    break
                data += subdata
                headend = data.find("\r\n\r\n")
                if headend > 0:
                    break
            fp.seek(0)
        else:
            data = param["toprocess"]
            headend = data.find("\r\n\r\n")
            fp = StringIO(data)
        if headend > 0:
            headlist = data[0:headend].split("\r\n")
        else:
            headlist = data.split("\r\n")
        first_line = headlist.pop(0)
        self.command, self.path, self.http_version, =  re.split('\s+', first_line)
        indexlist = self.path.split('?')
        self.baseuri = indexlist[0]
        indexlist = self.baseuri.split('/')
        while len(indexlist) != 0:
            self.index = indexlist.pop()
            if self.index == "":
                continue
            else:
                self.action,self.method = os.path.splitext(self.index)
                self.method = self.method.replace('.', '')
                break
        self.headers = {}
        for item in headlist:
            if item.strip() == "":
                continue
            segindex = item.find(":")
            if segindex < 0:
                continue
            key = item[0:segindex].strip()
            value = item[segindex+1:].strip()
            self.headers[key.lower()] = value

        self.command = self.command.lower()
        self.getdic = {}
        self.form = {}
        self.filedic = {}
        self.body = ""
        if self.command  == "get" and "?" in self.path:
            myparse_qs(self.path.split("?").pop(), self.getdic)
            #for key in self.getdic:
            #    self.getdic[key] = self.getdic[key][0]
        elif self.command == "post" and self.headers.get('content-type',"").find("boundary") > 0:
            cgiform = cgi.FieldStorage(fp=fp,headers=None,
                    environ={'REQUEST_METHOD':self.command,'CONTENT_TYPE':self.headers['content-type'],})
            for key in cgiform:
                fileitem = cgiform[key]
                if fileitem.filename == None:
                    self.form[key] = fileitem.file.read()
                else:
                    self.filedic[key] = fileitem
        elif self.command == "post":
            self.body = data[headend+4:]
            myparse_qs(self.body, self.form)
            #for key in self.form:
            #    self.form[key] = self.form[key][0]
        if "rc" in param:
            param["rc"].close()
            del param["rc"]

def ListIndex(path):
    cont = """<html><head><meta http-equiv="Content-Type" content="text/html; charset=UTF-8">"""
    cont += """<title>Index of %s</title></head><body bgcolor="white">""" % path
    cont += "<h1>Index of %s</h1><hr><pre>" % path
    while path.find("//") != -1:
        path = path.replace("//", "/")
    path_list = path.split("/")
    if len(path_list) > 3:
        path_list.pop() 
        path_list.pop() 
        p_path = "/".join(path_list) + "/"
        cont += """<a href="%s">../</a>\n""" % p_path
    filelist = os.listdir("."+path)
    for f in filelist:
        fname = path + f
        if not os.path.isfile("."+fname):
            fname += "/"
        cont += """<a href="%s">%s</a>\n""" % (fname, f)
    cont += "</pre><hr></body></html>"
    return cont

def sendfilejob( request, data, epoll_fd, fd):
    try:
        if request.baseuri[-1] == '/':
            res = ListIndex(request.baseuri)
            data["writedata"] = "HTTP/1.1 200 OK\r\nContent-Length: %s\r\nConnection:keep-alive\r\n\r\n%s" % (len(res),res)
        else:
            base_filename = request.baseuri[request.baseuri.find(static_dir)+1:]
            cache_filename = "./cache_"+base_filename
            filename = "./"+base_filename
            return_content_type = None
            if not os.path.exists(filename) or ".." in base_filename:
                res = "404 Not Found"
                data["writedata"] = "HTTP/1.1 404 Not Found\r\nContent-Length: %s\r\nConnection:keep-alive\r\n\r\n%s" % (len(res),res)
                logger.warn(" fail: %s not found" % (request.path))
            else:
                lasttimestr = request.headers.get("if-modified-since", None)
                filemd5 = os.path.getmtime(filename)
                ctime = os.path.getctime(filename)
                timestr = time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime(filemd5))
                curtime = time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime(time.time()))
                sock = data["connections"]
                if lasttimestr == timestr and "range" not in request.headers:
                    data["writedata"] = "HTTP/1.1 304 Not Modified\r\nLast-Modified: %s\r\nETag: \"%s\"\r\nDate: %s\r\nConnection:keep-alive\r\n\r\n" % (timestr,filemd5,curtime)
                else:
                    ext = request.method
                    iszip = False
                    Accept_Encoding = request.headers.get("accept-encoding", "")
                    ext_upper = ext.upper()
                    return_content_type = mimedic.get(ext_upper, None)
                    if ("range" not in request.headers and ext_upper in gzipdic) or \
                            (ext == "" and "gzip" in Accept_Encoding and os.path.getsize(filename) < 1024*1024*5):
                        need_zip = False
                        if not os.path.exists(cache_filename):
                            need_zip = True
                        else:
                            cache_mtime = os.path.getmtime(cache_filename)
                            if cache_mtime < ctime or cache_mtime < filemd5:
                                need_zip = True
                        if need_zip:
                            d,f = os.path.split(cache_filename)
                            try:
                                if not os.path.exists(d):
                                    os.makedirs(d)
                                f_out = gzip.open(cache_filename, 'wb')
                                f_out.write(open(filename).read())
                                f_out.close()
                            except Exception, e:
                                print str(e)
                                pass
                        filename = cache_filename
                        iszip = True


                    filesize = os.path.getsize(filename)
                    if "range" in request.headers:
                        range_value = request.headers["range"].strip(' \r\n')
                        range_value = range_value.replace("bytes=", "")
                        start,end = range_value.split('-')
                        if end == '':
                            end = filesize - 1
                        start = int(start)
                        end = int(end)
                        headstr = "HTTP/1.1 206 Partial Content\r\nLast-Modified: %s\r\nETag: \"%s\"\r\nDate: %s\r\n" % (timestr,filemd5,curtime)
                        headstr += "Accept-Ranges: bytes\r\nContent-Range: bytes %s-%s/%s\r\n" % (start,end,filesize)
                    else:
                        start = 0
                        end = filesize - 1
                        headstr = "HTTP/1.1 200 OK\r\nAccept-Ranges: bytes\r\nLast-Modified: %s\r\nETag: \"%s\"\r\nDate: %s\r\n" % (timestr,filemd5,curtime)
                        if return_content_type != None:
                            headstr += "Content-Type: %s\r\n" % return_content_type
                    offset = start
                    totalsenlen = end - start + 1
                    if totalsenlen < 0:
                        totalsenlen = 0
                    if iszip:
                        headstr += "Content-Encoding: gzip\r\n"
                    headstr += "Content-Length: %s\r\nConnection:keep-alive\r\n" % totalsenlen
                    headstr += "\r\n"
                    f = open(filename)
                    f.seek(offset)
                    readlen = 102400
                    if readlen > totalsenlen:
                        readlen = totalsenlen
                    firstdata = f.read(readlen)
                    headstr += firstdata
                    totalsenlen -= len(firstdata)
                    data["f"] = f
                    data["totalsenlen"] = totalsenlen
                    data["writedata"] = headstr
                logger.info(" success: %s" % (request.path))
    except Exception, e:
        logger.error(" fail: %s %s" % (request.path, str(e)+getTraceStackMsg()))
        res = "404 Not Found"
        data["writedata"] = "HTTP/1.1 404 Not Found\r\nContent-Length: %s\r\nConnection:keep-alive\r\n\r\n%s" % (len(res),res)
        pass
    try:
        epoll_fd.modify(fd, select.EPOLLOUT | select.EPOLLIN | select.EPOLLERR | select.EPOLLHUP)
    except Exception, e:
        #print str(e)+getTraceStackMsg()
        pass

class Worker(object):

    def __init__(self):
        self._obj_dict = {}
        self._mtime_dict = {}

        for l in listfile:
            if l == str(__file__):
                continue
            key, extname = os.path.splitext(l)
            if extname == ".py"  and key in sys.modules:
                try:
                    action = sys.modules[key]
                    self._obj_dict[key] = eval("action.%s()" % key)
                except Exception, e:
                    #print str(e)+getTraceStackMsg()
                    continue
                self._mtime_dict[key] = action_time[key]

    def getGloalAction(self, action_key):
        action = sys.modules.get(action_key, None)
        auto_update = False
        if action == None:
            auto_update = True
        else:
            try:
                auto_update = action.FastpyAutoUpdate
            except Exception, e:
                pass
        if not auto_update:
            return auto_update,None,None
        if action == None:
            print action_key 
            action = __import__(action_key)
            mtime = os.path.getmtime("./%s.py" % action_key)
            action_time[action_key] = mtime
        else:
            load_time = action_time[action_key]
            mtime = os.path.getmtime("./%s.py" % action_key)
            if mtime>load_time:
                try:
                    del sys.modules[action_key]
                    del action
                except Exception, e:
                    pass
                action = __import__(action_key)
                action_time[action_key] = mtime
        return auto_update,action,mtime

    def process(self, data, epoll_fd, fd):
        res = ""
        add_head = ""
        headers = {}
        try:
            request = QuickHTTPRequest(headers,data,epoll_fd,fd)
            request.parse(data)
        except Exception, e:
            print str(e)+getTraceStackMsg()
            res = "http format error"
        try:
            headers["Content-Type"] = "text/html;charset=utf-8"
            headers["Connection"] = "keep-alive"
            if request.baseuri == "/favicon.ico":
                request.baseuri = "/"+static_file_dir+request.baseuri
            if static_dir in request.baseuri or "favicon.ico" in request.baseuri:
                sendfilejob(request,data,epoll_fd,fd)
                return None
            action_key = request.action
            obj = self._obj_dict.get(action_key, None)
            load_time = self._mtime_dict.get(action_key, None)
            auto_update,action,mtime = self.getGloalAction(action_key)
            if auto_update and (obj == None or load_time == None or mtime>load_time):
                self._mtime_dict[action_key] = mtime
                obj = eval("action.%s()" % action_key)
                self._obj_dict[action_key] = obj

            method = getattr(obj, request.method)
            res = method(request, headers)
            if res == None:
                return None
            if headers.get("Content-Encoding","") == "gzip":
                buf = StringIO()
                f = gzip.GzipFile(mode='wb', fileobj=buf)
                f.write(res)
                f.close()
                res = buf.getvalue()
            logger.info(" success: %s" % (request.path))
        except Exception, e:
            logger.error(" fail: %s " % (str(e)+getTraceStackMsg()))
            res = "404 Not Found"
        try:
            if headers.get("Connection","") == "close":
                data["keepalive"] = False
            res_len = len(res)
            headers["Content-Length"] = res_len
            for key in headers:
                add_head += "%s: %s\r\n" % (key, headers[key])
            if res == "404 Not Found":
                data["writedata"] = "HTTP/1.1 404 Not Found\r\n%s\r\n%s" % (add_head, res)
            else:
                data["writedata"] = "HTTP/1.1 200 OK\r\n%s\r\n%s" % (add_head, res)
            if "read_cache_name" in data:
                os.remove(data["read_cache_name"])
                del data["read_cache_name"]
            epoll_fd.modify(fd, select.EPOLLOUT | select.EPOLLIN | select.EPOLLERR | select.EPOLLHUP)
        except Exception, e:
            print data["toprocess"]
            print data["writedata"]
            print "error fd:",fd
            print str(e)+getTraceStackMsg()

#def InitLog():
#    logging.config.fileConfig('logging.conf')  
#    root_logger = logging.getLogger('root')  
#    root_logger.debug('test root logger...')  
#    logger = logging.getLogger('main')  
#    logger.info('test main logger')  

class MyThread(threading.Thread):
    ind = 0
    def __init__(self, threadCondition, shareObject, **kwargs):
        threading.Thread.__init__(self, kwargs=kwargs)
        self.threadCondition = threadCondition
        self.shareObject = shareObject
        self.setDaemon(True)
        self.worker = Worker()


    def processer(self, param, epoll_fd, fd):
        try:
            self.worker.process(param, epoll_fd, fd)
        except:
            print  "job error:" + getTraceStackMsg()


    def run(self):
        while True:
            try:
                param, epoll_fd, fd = self.shareObject.get()
                self.processer(param, epoll_fd, fd)
            except Queue.Empty:
                continue
            except :
                print "thread error:" + getTraceStackMsg()


class ThreadPool:
    def __init__( self, num_of_threads=10):
        self.threadCondition=threading.Condition()
        self.shareObject=Queue.Queue()
        self.threads = []
        self.__createThreadPool( num_of_threads )


    def __createThreadPool( self, num_of_threads ):
        for i in range( num_of_threads ):
            thread = MyThread( self.threadCondition, self.shareObject)
            self.threads.append(thread)


    def start(self):
        for thread in self.threads:
            thread.start()


    def add_job( self, param, epoll_fd, fd ):
        self.shareObject.put( (param, epoll_fd, fd) )

def process_http(param, tp, epoll_fd, fd, work, datas, read_len):
    param["read_len"] = read_len
    len_s = -1
    len_e = -1
    contentlen = param.get("contentlen", -1)
    headlen = param.get("headlen", -1)
    if contentlen == -1:
        len_s = datas.find("Content-Length:")
        if len_s < 0:
            len_s = datas.lower().find("content-length:")
        if len_s > 0:
            len_e = datas.find("\r\n", len_s)
        if len_s > 0 and len_e > 0 and len_e > len_s+15:
            len_str = datas[len_s+15:len_e].strip()
            if len_str.isdigit():
                contentlen = int(datas[len_s+15:len_e].strip())
                param["contentlen"] = contentlen
    if contentlen > MaxReadSize:
        clearfd(epoll_fd,params,fd)
        return 
    if headlen == -1:
        headend = datas.find("\r\n\r\n")
        if headend > 0:
            headlen = headend + 4
            param["headlen"] = headlen
    if ": multipart/form-data; boundary" in datas and \
       len(datas) > 1024*1024*3 and "rc" not in param:
        if headlen > 0 and contentlen > 0:
            param["rc"] = open("%s/%s_%s.tmp" % (read_cache_dir,pid,fd), "w")
            pass
        else:
            clearfd(epoll_fd,params,fd)
            return
    if "rc" in param:
        param["rc"].write(datas)
        param["readdata"] = ""
    else:
        param["readdata"] = datas
    toprocess = param.get("toprocess", "")
    if "" == toprocess and \
            ((contentlen >= 0 and headlen > 0 and (contentlen + headlen) <= read_len) or \
            (contentlen == -1 and headlen > 0 and headlen <= read_len)):
        if "rc" in param:
            param["rc"].close()
            param["read_cache_name"] = "%s/%s_%s.tmp" % (read_cache_dir,pid,fd)
            param["rc"] = open(param["read_cache_name"], "r")
            read_len = 0
        else:
            one_http_len = headlen
            if contentlen > 0:
                one_http_len += contentlen
            param["toprocess"] = param["readdata"][0:one_http_len]
            param["readdata"] = param["readdata"][one_http_len:]
            read_len = read_len - one_http_len
            #logger.error(json.dumps(param["addr"])+param["toprocess"])
        param["contentlen"] = -1
        param["headlen"] = -1
        param["read_len"] = read_len
        #tp.add_job(param,epoll_fd,fd)
        epoll_fd.modify(fd, select.EPOLLERR | select.EPOLLHUP)
        if Install_gevent:
            gevent.spawn(CoroutineResume,work,param,epoll_fd,fd);
        else:
            work.process(param,epoll_fd,fd)

def check_next_http(param, tp, epoll_fd, fd, work):
    datas = param.get("readdata", "")
    if "" == datas:
        param["toprocess"] = ""
        return 0
    read_len = len(datas)
    contentlen = param.get("contentlen", -1)
    headlen = param.get("headlen", -1)
    if contentlen == -1:
        len_s = datas.find("Content-Length:")
        if len_s < 0:
            len_s = datas.lower().find("content-length:")
        if len_s > 0:
            len_e = datas.find("\r\n", len_s)
        if len_s > 0 and len_e > 0 and len_e > len_s+15:
            len_str = datas[len_s+15:len_e].strip()
            if len_str.isdigit():
                contentlen = int(datas[len_s+15:len_e].strip())
                param["contentlen"] = contentlen
    if headlen == -1:
        headend = datas.find("\r\n\r\n")
        if headend > 0:
            headlen = headend + 4
            param["headlen"] = headlen
    if (contentlen >= 0 and headlen > 0 and (contentlen + headlen) <= read_len) or \
           (contentlen == -1 and headlen > 0 and headlen <= read_len):
        one_http_len = headlen
        if contentlen > 0:
            one_http_len += contentlen
        param["toprocess"] = param["readdata"][0:one_http_len]
        param["readdata"] = param["readdata"][one_http_len:read_len]
        read_len = read_len - one_http_len
        param["contentlen"] = -1
        param["headlen"] = -1
        param["read_len"] = read_len
        #tp.add_job(param,epoll_fd,fd)
        epoll_fd.modify(fd, select.EPOLLERR | select.EPOLLHUP)
        if Install_gevent:
            gevent.spawn(CoroutineResume,work,param,epoll_fd,fd);
        else:
            work.process(param,epoll_fd,fd)
        return one_http_len
    else:
        param["toprocess"] = ""
        return 0

def clearfd(epoll_fd, params, fd):
    try:
        epoll_fd.unregister(fd)
    except Exception, e:
        #print str(e)+getTraceStackMsg()
        pass

    try:
        param = params[fd]
        soc = param["connections"]
        soc.shutdown(1)
        soc.close()
        f = param.get("f", None)
        if f != None:
            f.close()
        rc = param.get("rc", None)
        if rc != None:
            rc.close()
        if "read_cache_name" in param:
            os.remove(param["read_cache_name"])
    except Exception, e:
        #print str(e)+getTraceStackMsg()
        pass

    try:
        del params[fd]
        #logger.error(getTraceStackMsg())
        #logger.error("clear fd:%s" % fd)
    except Exception, e:
        #print str(e)+getTraceStackMsg()
        pass

def run_main(listen_fd):
    try:
        epoll_fd = select.epoll()
        epoll_fd.register(listen_fd.fileno(), select.EPOLLIN | select.EPOLLERR | select.EPOLLHUP)
    except select.error, msg:
        logger.error(msg)


    #tp = ThreadPool(thread_num)
    #tp.start()
    tp = None
    work = Worker()
    pid = os.getpid()

    params = {}


    last_min_time = -1
    while True:
        if Install_gevent:
            gevent.sleep(0)
        epoll_list = epoll_fd.poll(0.001)

        cur_time = 0
        if len(epoll_list) > 0:
            cur_time = time.time()
            #check time out
            if cur_time - last_min_time > 600:
                last_min_time = cur_time
                objs = params.items()
                for (key_fd,value) in objs:
                    fd_time = value.get("time", 0)
                    del_time = cur_time - fd_time
                    if del_time > 600:
                        clearfd(epoll_fd,params,key_fd)
                    elif fd_time < last_min_time:
                        last_min_time = fd_time

        for fd, events in epoll_list:
            if fd == listen_fd.fileno():
                while True:
                    try:
                        conn, addr = listen_fd.accept()
                        conn.setblocking(0)
                        epoll_fd.register(conn.fileno(), select.EPOLLIN | select.EPOLLERR | select.EPOLLHUP)
                        conn.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                        #conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, True)
                        params[conn.fileno()] = {"addr":addr,"writelen":0, "connections":conn, "time":cur_time}
                    except socket.error, msg:
                        break
            elif select.EPOLLIN & events:
                param = params.get(fd,None)
                if param == None:
                    continue
                param["time"] = cur_time
                datas = param.get("readdata","")
                cur_sock = params[fd]["connections"]
                read_len = param.get("read_len", 0)
                while True:
                    try:
                        data = cur_sock.recv(102400)
                        if not data:
                            if read_len != 0:
                                param["closeafterresponse"] = 1
                                process_http(param, tp, epoll_fd, fd, work, datas, read_len)
                            else:
                                clearfd(epoll_fd,params,fd)
                            break
                        else:
                            datas += data
                            read_len += len(data)
                    except socket.error, msg:
                        if msg.errno == errno.EAGAIN:
                            try:
                                process_http(param, tp, epoll_fd, fd, work, datas, read_len)
                                break
                            except Exception as e:
                                print str(e)
                        else:
                            clearfd(epoll_fd,params,fd)
                            break
            elif select.EPOLLHUP & events or select.EPOLLERR & events:
                clearfd(epoll_fd,params,fd)
                #logger.error("sock: %s error" % fd)
            elif select.EPOLLOUT & events:
                param = params.get(fd,None)
                if param == None:
                    continue
                param["time"] = cur_time
                sendLen = param.get("writelen",0)
                writedata = param.get("writedata", "")
                total_write_len = len(writedata)
                cur_sock = param["connections"]
                f = param.get("f", None)
                totalsenlen = param.get("totalsenlen", None)
                if writedata == "":
                    clearfd(epoll_fd,params,fd)
                    continue
                while True:
                    try:
                        sublen = cur_sock.send(writedata[sendLen:])
                        if sublen <= 0:
                            clearfd(epoll_fd,params,fd)
                            param["writelen"] = sendLen
                            break
                        sendLen += sublen
                        if sendLen >= total_write_len:
                            if f != None and totalsenlen != None:
                                readmorelen = 102400
                                if readmorelen > totalsenlen:
                                    readmorelen = totalsenlen
                                morefiledata = ""
                                if readmorelen > 0:
                                    morefiledata = f.read(readmorelen)
                                if morefiledata != "":
                                    writedata = morefiledata
                                    sendLen = 0
                                    total_write_len = len(writedata)
                                    totalsenlen -= total_write_len
                                    param["writedata"] = writedata
                                    param["totalsenlen"] = totalsenlen
                                    continue
                                else:
                                    f.close()
                                    del param["f"]
                                    del param["totalsenlen"]
                            if param.get("keepalive", True) and "closeafterresponse" not in param:
                                param["writedata"] = ""
                                param["writelen"] = 0
                                epoll_fd.modify(fd, select.EPOLLIN | select.EPOLLERR | select.EPOLLHUP)
                                check_next_http(param, tp, epoll_fd, fd, work)
                            else:
                                clearfd(epoll_fd,params,fd)
                            break
                    except socket.error, msg:
                        if msg.errno == errno.EAGAIN:
                            param["writelen"] = sendLen
                            break
                        clearfd(epoll_fd,params,fd)
                        break
            else:
                continue



if __name__ == "__main__":
    reload(sys)
    sys.setdefaultencoding('utf8')
    #InitLog()
    port = int(sys.argv[1])
    try:
        listen_fd = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
    except socket.error, msg:
        logger.error("create socket failed")
    try:
        listen_fd.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    except socket.error, msg:
        logger.error("setsocketopt SO_REUSEADDR failed")
    try:
        listen_fd.bind(('', port))
    except socket.error, msg:
        logger.error("bind failed")
    try:
        listen_fd.listen(10240)
        listen_fd.setblocking(0)
    except socket.error, msg:
        logger.error(msg)


    child_num = 1
    c = 0
    while c < child_num:
        c = c + 1
        newpid = os.fork()
        if newpid == 0:
            run_main(listen_fd)
    run_main(listen_fd)
