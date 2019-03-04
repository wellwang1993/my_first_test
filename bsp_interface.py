#-*- coding:utf-8 -*-
import re
import logging
import logging.config

import json
from multiprocessing import Process, Manager
import sys
import os
import thread
import datetime
import time
import hashlib
import json
import subprocess


manager = Manager()

logging.config.fileConfig('logging.conf')
logger=logging.getLogger('root')
pat_priority = re.compile(r'.*priority:(\d+)')
OriFlowAdjust="FlowAdjust.conf.bsp"
OriFlowDomain="FlowAllDomain.conf.bsp"
OriFlowNameid="FlowAllNameid.conf.bsp"
OriFlowHotUri="FlowHotUri.conf.bsp"

FlowChannelHot = "FlowChannelHot.conf.bsp"

FlowAdjust="FlowAdjust.conf.bsp.new"
FlowDomain="FlowAllDomain.conf.bsp.new"
FlowNameid="FlowAllNameid.conf.bsp.new"
FlowHotUri="FlowHotUri.conf.bsp.new"
#1. add "status", "modify_time", "indate", "out_service_time" 
#2. 
_version = "1.0.0.2"
def getinfo(vip):
    try:
        team_key = "ssr-team"
        eintry_key = '72b3271d737763ae2c2abbd7f07b4eb3'
        now = str(time.time()).split('.')[0]
        token_ori = "{}{}{}".format(team_key,eintry_key,now)
        m1 = hashlib.md5()
        m1.update(token_ori.encode("utf-8"))
        token = m1.hexdigest()
        params = "access_id={}&timestamp={}&token={}".format(team_key,now,token)
         
        url = 'https://ris.chinacache.com/v3/resource/server?{}&field=toptiernode&description={}&limit=1'.format(params,vip)
        full_url = "curl -H 'Content-Type:application/json' -ks '{}'".format(url)
        p = subprocess.Popen(full_url,shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        stdout,stderr = p.communicate()
        if(p.returncode == 0):
            if len(stdout)>0:
                res = json.loads(stdout)
                if res.get('status') != None and res.get('status')==0:
                    if res.get('data') != None:
                        res = res['data']
                        if res and res.get('list') != None and len(res['list']) >0:
                            val = res['list'][0]
                            if val !=None and val.get('nodes') !=None and len(val['nodes']) >0:
                                val = val['nodes'][0]
                                if val!=None and val.get('toptier_nodes') != None and len(val['toptier_nodes']) >0:
                                    val = val['toptier_nodes'][0]
                                    if val!=None and val.get('description')!=None:
                                        first_node_name = val['description']
                                        return first_node_name
        logger.info(full_url)
    except Exception as err:
        print err
        logger.error(err)
def getnode(hostname):
    try:
        node_desc = None
        if node_devname.get(hostname) != None:
            node_desc = node_devname[hostname]
        else:
            with open("node_devname_cache",'r') as f:
                for line in f.readlines():
                    line = line.split(' ')
                    if line !=None and len(line) == 2:
                        node_devname[line[0].strip('\r\n')] = line[1].strip('\r\n')
            f.close()
            node_desc = getinfo(hostname)
            if node_desc!=None and node_devname.get(hostname) == None:
                node_devname[hostname] = node_desc
                with open("node_devname_cache","a") as fw:
                    fw.write("{} {}\n".format(hostname,node_desc))
                fw.close()
        return node_desc
    except Exception as err:
        logger.error(err)

node_devname= {}
with open("node_devname_cache",'r') as f:
    for line in f.readline():
        line = line.split(" ")
        if line !=None and len(line) == 2:
            node_devname[line[0]] = line[1]

def serialize_instance(obj):
    d = {}
    d.update(vars(obj))
    return d
class CHANNEL_HOT:
    def __init__(self):
        self.domain = ""
        self.bandwidth = {}
        self.hot_uri_ratio = ""
        self.warm_uri_ratio = 0.0
        self.cold_uri_ratio = ""
    def gen_obj(self,k,v):
        self.domain = v['domain']
        self.hot_uri_ratio = v['hot_uri_ratio']
        self.warm_uri_ratio = v['warm_uri_ratio']
        self.cold_uri_ratio = v['cold_uri_ratio']
        self.bandwidth = v['bandwidth'][k]
        return self
    def file_gen_obj(self,v):
        self.domain = v['domain']
        self.hot_uri_ratio = v['hot_uri_ratio']
        self.warm_uri_ratio = v['warm_uri_ratio']
        self.cold_uri_ratio = v['cold_uri_ratio']
        self.bandwidth = v['bandwidth']
        return self
    def genghr(self):
        return '{}|{}|{}|{}|{}'.format(self.domain,self.bandwidth,self.hot_uri_ratio,self.warm_uri_ratio,self.cold_uri_ratio) 
    def __str__(self):
        return '{}-{}-{}-{}-{}'.format(self.domain,self.bandwidth,self.hot_uri_ratio,self.warm_uri_ratio,self.cold_uri_ratio)
        

class BSP_BODY:
    def __init__(self):
        self.date_time = ""
        self.domain = ""
        self.modify_time = ""
        self.upper_bandwidth = ""
        self.lower_bandwidth = ""
        self.to_nameid = ""
        self.location = ""
        self.node_name = ""
        self.adjust_type = ""
        self.indate = ""
        self.out_service_time = ""
        self.region = ""
        self.create_type = ""
        self.id = ""
    
        self.adjust_percent = ""
        self.cmd_id = ""
        self.status = ""
        self.province = ""
        self.priority = ""

    def toOriString(self):
        return \
    "{},{},{},{},{},{},{},{},{},{},{},{},{}".format(self.domain,self.location,self.adjust_percent,self.to_nameid,self.node_name,self.date_time,self.create_type,self.cmd_id,self.status,self.modify_time,self.indate,self.out_service_time,self.province) 
    def toOriGHRString(self):
        return \
    "{},{},{},{}".format(self.domain,self.location,self.adjust_percent,self.to_nameid)
    
    def toString(self):
        return \
                'date_time:{},domain:{},modify_time:{},upper_bandwidth:{},lower_bandwidth:{},to_nameid:{},location:{},node_name:{},adjust_type:{},indate:{},out_service_time:{},region:{},create_type:{},priority:{},id:{}'.format(self.date_time,self.domain,self.modify_time,self.upper_bandwidth,self.lower_bandwidth,self.to_nameid,self.location,self.node_name,self.adjust_type,self.indate,self.out_service_time,self.region,self.create_type,self.priority,self.id)
    
    def toGHRString(self):
        ghr_list = []
        for toNameid in self.to_nameid:
            for tonameid,bandwidth in toNameid.items():
                ghrobj ="{},{},lower_bandwidth:{},upper_bandwidth:{},date_time:{},out_service_time:{},{},{},{},priority:{}".format(self.domain,self.location,self.lower_bandwidth,self.upper_bandwidth,self.date_time,self.out_service_time,bandwidth['available_bandwidth'],tonameid,self.adjust_type,self.priority)
                ghr_list.append(ghrobj)
        return ghr_list
    
    def gen_obj(self,body_dict):
        self.date_time = body_dict['date_time']
        self.domain = body_dict['domain']
        self.modify_time = body_dict['modify_time']
        self.upper_bandwidth = body_dict['upper_bandwidth']
        self.lower_bandwidth = body_dict['lower_bandwidth']
        self.to_nameid = body_dict['to_nameid']        
        self.location = body_dict['location']
        self.node_name = body_dict['node_name']
        self.adjust_type = body_dict['adjust_type']
        self.indate = body_dict['indate']
        self.out_service_time = body_dict['out_service_time']
        self.region = body_dict['region']
        self.create_type = body_dict['create_type']
        self.priority = body_dict['priority']
        self.id = body_dict['id']
        
        del self.adjust_percent
        del self.cmd_id
        del self.status
        del self.province
        return self
    def gen_ori_obj(self,body_dict):
        self.date_time = body_dict['date_time']
        self.domain = body_dict['domain']
        self.adjust_percent = body_dict['adjust_percent']
        self.to_nameid = body_dict['to_nameid']        
        self.location = body_dict['location']
        self.node_name = body_dict['node_name']
        self.create_type = body_dict['create_type']
        if body_dict['cmd_id']: 
            self.cmd_id = body_dict['cmd_id'].strip('\n')
        if body_dict['status']: 
            self.status = body_dict['status'].strip('\n')
        if body_dict['modify_time']: 
            self.modify_time = body_dict['modify_time'].strip('\n')
        if body_dict['indate']: 
            self.indate = body_dict['indate'].strip('\n')
        if body_dict['out_service_time']: 
            self.out_service_time = body_dict['out_service_time'].strip('\n')
        if body_dict['province']:
            self.province = body_dict['province'].strip('\n')
        del self.upper_bandwidth
        del self.lower_bandwidth
        del self.adjust_type
        del self.region
        del self.id
        del self.priority
        return self

    def gen_obj_byfileline(self,line):
        split = line.split(',')
        self.domain = split[0]        
        self.location = split[1]
        self.adjust_percent = split[2]
        self.to_nameid = split[3]        
        self.node_name = split[4]
        self.date_time = split[5]
        self.create_type = split[6]
        self.cmd_id = split[7].strip('\n')
        if len(split)>8:
            self.status = split[8]
            self.modify_time = split[9]
            self.indate = split[10]
            self.out_service_time = split[11].strip('\n')
            self.province = split[12].strip('\n')
        del self.upper_bandwidth
        del self.lower_bandwidth
        del self.adjust_type
        del self.region
        del self.id
        del self.priority
        return self

class A:
    def __init__(self):
        self.name = ""
    def toString(self):
        return "{}".format(self.name)
    def toOriString(self):
        return "{}".format(self.name)
    
    def gen_ori_obj(self,v):
        self.name = v
        return self
    def gen_obj(self,v):
        self.name = v
        return self
class HOT:
    def __init__(self):
        self.timestamp = ""
        self.domain = ""
        self.delimiter = ""
        self.type = ""
        self.uri = ""
    def toOriGHRString(self):
        return "{},{}".format(self.domain,self.uri)
    def toOriString(self):
        return "{},{},{}".format(self.timestamp,self.domain,self.uri)
    def toGHRString(self):
        return\
    '{},{},{}'.format(self.domain,self.type,self.uri)
    def toString(self):
        return\
    'timestamp:{},domain:{},delimiter:{},type:{},uri:{}'.format(self.timestamp,self.domain,self.delimiter,self.type,self.uri)
    def gen_obj(self,v):
        self.timestamp = v['timestamp']
        self.domain = v['domain']
        self.delimiter = "," # feel strange....
        self.type = v['type']
        self.uri = v['uri']
        return self
    def gen_ori_obj(self,v):
        self.timestamp = v['timestamp']
        self.domain = v['domain']
        self.delimiter = "," # feel strange....
        self.uri = v['uri']
        del self.type
        return self
    def read_file(self,hotfile):
        res = []
        if os.path.exists(hotfile):
            with open(hotfile,'r') as f:
                for line in f.readlines():
                    splits = line.strip("\r\n").split(',')
                    if len(splits) > 2:
                        hot = HOT()
                        hot.timestamp = splits[0]               
                        hot.domain = splits[1]                   
                        hot.delimiter = ","
                        hot.uri = splits[2]
                        del hot.type
                        res.append(hot)
        return res
#adjust_list = manager.list()


adjust_dict = {}
domain_list = []
nameid_list = []
hot_uri_list = []
channel_hoturi = {}

ori_adjust_list = []
ori_domain_list = []
ori_nameid_list = []
ori_hot_uri_list = []
class bsp_interface(object):

    def put_channel_hoturi(self,request,response_head):
        global channel_hoturi
        params_dict = request.body
        if params_dict:
            logger.info('put channel hoturi the uri is %s ' % params_dict)
            tmp_list = json.loads(params_dict)
            if len(tmp_list) > 0:
                if channel_hoturi:
                    channel_hoturi.clear()
                for v in tmp_list:
                    for k in v['bandwidth']:
                        if channel_hoturi.get(k) == None:
                            channel_hoturi[k] = []
                        channel_hoturi[k].append(CHANNEL_HOT().gen_obj(k,v))
                with open(FlowChannelHot,"w") as f:
                    json.dump(channel_hoturi,f,default=serialize_instance)
                return "success"
            else:
                logger.info("put channel hoturi the content is empty...")
                return "success"
    def ghr_get_channel_hoturi(self,request,response_head):
        params = request.getdic
        host = params['hostname']
        global channel_hoturi
        logger.debug("get ghr channel hoturi  ,the  memorydict is %s ,the deviceis %s" % (json.dumps(channel_hoturi,default=serialize_instance),host))
        if host:
            #node_name = "-".join(host.split('-')[0:-2]).upper()
            node_name = getnode(host)
            if node_name ==None:
                logger.error('channel nodename is nil the dev is {} '.format(host))
            if channel_hoturi:
                if channel_hoturi.get(node_name):
                    tmp_list = []
                    for obj in channel_hoturi[node_name]:
                        tmp_list.append(obj.genghr())
                    return '\n'.join(tmp_list)
                else:
                    logger.error("the node has no channel hoturi info..the device is %s " % (host))
                    return ""
            else:
		try:
                    with open(FlowChannelHot,"r") as f:
                        channel_hoturi_tmp = json.load(f)
                        tmp_list = []
                        for k,v in channel_hoturi_tmp.items():
                            if channel_hoturi.get(k) == None:
                                channel_hoturi[k] = []
                            for item in v:
                                obj = CHANNEL_HOT().file_gen_obj(item)
                                channel_hoturi[k].append(obj)
                                if k == node_name:
                                        tmp_list.append(obj.genghr())
                        if tmp_list:
                                return '\n'.join(tmp_list)
                    logger.error("the node has no channel hoturi info..the device is %s " % (host))
                    return ""
                except Exception as err:
                        logger.error(err)
                return ""
                    
    def delete_adjust(self, request, response_head):
        return deal_adjust_bsp_cmd(request,FlowAdjust ,BSP_BODY,"del")
    def put_adjust(self, request, response_head):
        params_dict = request.form
        if params_dict.get('adjust_body'):
            deal_old_bsp_cmd(params_dict,ori_adjust_list,OriFlowAdjust,BSP_BODY)
            return 'success' 
        else:
            return deal_adjust_bsp_cmd(request,FlowAdjust ,BSP_BODY,"add")
    def put_hoturi(self, request, response_head):
        params_dict = request.form
        if params_dict.get('adjust_body'):
            deal_old_bsp_cmd(params_dict,ori_hot_uri_list,OriFlowHotUri,HOT)
            return 'success'
        else:
            params_dict = request.body
            logger.info('new api put hoturi the uri is %s ' % params_dict)
            if params_dict:
                tmp_list = []
                json_dict = json.loads(params_dict)
    #    json_dict = json.loads(params_dict.get('body'))
                if json_dict != None and len(json_dict) == 0:
                    logger.error('bsp empty command...'+params_dict)
                    os.rename(FlowHotUri,FlowHotUri+'.bak') 
                    del hot_uri_list[:]
                for v in json_dict:
                    tmp_list.append(HOT().gen_obj(v))
                if len(tmp_list) > 0:
                    del hot_uri_list[:]
                    hot_uri_list.extend(tmp_list)
                    logger.info("success insert into hoturi"+json.dumps(hot_uri_list,default=serialize_instance))
            try:
                with open(FlowHotUri,'w') as f:
                    json.dump(hot_uri_list,f,default=serialize_instance)
                    return "success"
            except Exception as err:
                logger.error(str(err))
         #   with open(FlowHotUri,'w') as f:
          #      json.dump(hot_uri_list,f)
           #     return "success"

    def get_hoturi(self, request, response_head):
        header = request.headers
        if header.get("version") and header.get("version")=="v2":
            return bsp_get_response(request,response_head,hot_uri_list,FlowHotUri,HOT)
        else:
            logger.debug('old api get bsp,the file is %s,the memorydict is %s ' % (OriFlowHotUri,json.dumps(ori_hot_uri_list,default=serialize_instance)))
            if ori_hot_uri_list:
                return json.dumps(ori_hot_uri_list,default=serialize_instance)
            else:
                lists = HOT().read_file(OriFlowHotUri)
                return json.dumps(lists,default=serialize_instance)
    def get_adjust(self, request, response_head):
        header = request.headers
        if header.get("version") and header.get("version")=="v2":
            logger.debug("new api get bsp adjust ,the adjust memorydict is %s" % json.dumps(adjust_dict,default=serialize_instance))
            if adjust_dict:
                return json.dumps(adjust_dict.values(),default=serialize_instance);
            else:
                try:
                    with open("FlowAdjust.conf.bsp.new","r") as f:
                        adjust_li = json.load(f)
                    return json.dumps(adjust_li.values(),default=serialize_instance)
                except Exception as err:
                    logger.error(err)
                return json.dumps([])
        else:
            return readfile(request, response_head, ori_adjust_list, OriFlowAdjust)
    
    def ghr_get_hoturi(self, request, response_head):
        global ori_hot_uri_list
        logger.debug("old api get ghr hoturi  ,the hoturi memorydict is  %s " % json.dumps(ori_hot_uri_list,default=serialize_instance))
        res_body = []

        if len(ori_hot_uri_list) == 0:
            ori_hot_uri_list = HOT().read_file(OriFlowHotUri)
        for u in ori_hot_uri_list:
            res_body.append(u.toOriGHRString())
        return '\n'.join(res_body)
    
    def ghr_get_adjust(self, request, response_head):
        params = request.getdic
        host = params['hostname']
        logger.debug("old api get ghr adjust  ,the adjust memorydict is %s ,the deviceis %s" % (json.dumps(ori_adjust_list,default=serialize_instance),host))
        res_body = []
        if host:
            node_name = "-".join(host.split('-')[0:-1]).upper()
            if len(ori_adjust_list) == 0:
                init_local_bsp_file(ori_adjust_list,OriFlowAdjust)
            for obj in ori_adjust_list:
                if obj.node_name.upper() == node_name:
                    res_body.append(obj.toOriGHRString())
        
        return "\n".join(res_body)

    
    def ghr_get_domain(self,request,response_head):
        return ghr_get_response(request,response_head,domain_list,FlowDomain,A)
    def ghr_get_nameid(self,request,response_head):
        return ghr_get_response(request,response_head,nameid_list,FlowNameid,A)
    def ghr_get_hoturi_api(self,request,response_head):
        logger.debug("new api get ghr hot uri ,the hoturi memorydict is %s " % json.dumps(hot_uri_list,default=serialize_instance))
        if hot_uri_list:
            dict_obj = map(lambda x:x.toGHRString(),hot_uri_list)
            return '\n'.join(dict_obj)
        else:
            try:
                with open(FlowHotUri,'r') as f:
                    tmp_dict_obj = json.load(f)
                    tmp_dict_obj = map(lambda x:HOT().gen_obj(x).toGHRString(),tmp_dict_obj)
                    if tmp_dict_obj:
                        return '\n'.join(tmp_dict_obj)
            except Exception as err:
                logger.error(err)
            return ""
    def ghr_get_adjust_api(self, request, response_head):
        params = request.getdic
        logger.debug('new api get ghr adjust ,the adjust memorydict is %s ,the hostname is %s ' % (json.dumps(adjust_dict,default=serialize_instance),params))
        host = params['hostname']
        res_body = []
        if host:
            #node_name = "-".join(host.split('-')[0:-2]).upper()
            node_name = getnode(host)
            if node_name ==None:
                logger.error('nodename is nil the dev is {} '.format(host))
            if len(adjust_dict) == 0:
                try:
                    with open("FlowAdjust.conf.bsp.new",'r') as f:
                        ghr_adjust = json.load(f)
                        for _,obj in ghr_adjust.items():
                            obj = BSP_BODY().gen_obj(obj)
                            if obj.node_name== node_name:
                                res_body.extend(obj.toGHRString())
                except Exception as err:
                    logger.error(err)
            else:
                for k,obj in adjust_dict.items():
                    if obj.node_name.upper() == node_name:
                        if obj.node_name.upper() == node_name:
                            res_body.extend(obj.toGHRString())
            res_body.sort(key = lambda i:int(pat_priority.match(i).group(1)))
            if res_body:
                return "\n".join(res_body)
            else:
                return ""
    def put_domain(self, request, response_head):
        params_dict = request.form
        if params_dict.get('adjust_body'):
            deal_old_bsp_cmd(params_dict,ori_domain_list,OriFlowDomain,A)
        else:
            deal_common_bsp_cmd(request, domain_list, FlowDomain,A)
        return 'success' 
    def get_domain(self, request, response_head):
        header = request.headers
        if header.get("version") and header.get("version")=="v2":
            return bsp_get_response(request, response_head,domain_list,FlowDomain,A)
        else:
            return readfile(request, response_head, ori_domain_list, OriFlowDomain)
    def put_nameid(self, request, response_head):
        params_dict = request.form
        if params_dict.get('adjust_body'):
            deal_old_bsp_cmd(params_dict,ori_nameid_list,OriFlowNameid,A)
        else:
            deal_common_bsp_cmd(request, nameid_list, FlowNameid ,A)
        return 'success' 
    def get_nameid(self, request, response_head):
        header = request.headers
        if header.get("version") and header.get("version")=="v2":
            return bsp_get_response(request, response_head,nameid_list,FlowNameid,A)
        else:
            return readfile(request, response_head, ori_nameid_list, OriFlowNameid)
        
            
def init_local_bsp_file(lst,file):
    if lst == None or len(lst) == 0 :
        if os.path.isfile(file):
            with open(file,'r') as f:
                for line in f.readlines():
                    if line != None and len(line) > 0:
                        if len(line.split(',')) >= 8:
                            lst.append(BSP_BODY().gen_obj_byfileline(line))
        else:
            logger.error('no such file '+file)        
 


def bsp_get_response(request, response_head, dict_obj, file_obj,objclass):
    logger.debug('new api get bsp,the file is %s,the memorydict is %s ' % (file_obj,json.dumps(dict_obj,default=serialize_instance)))
    if dict_obj:
        return json.dumps(dict_obj,default=serialize_instance)
    else:
        try:
            with open(file_obj,'r') as f:
                tmp_dict_obj = json.load(f)
                return json.dumps(tmp_dict_obj,default=serialize_instance)
        except Exception as err:
            logger.error(err)
        return json.dumps([])

def ghr_get_response(request, response_head, dict_obj, file_obj,objclass):
    logger.debug('new api get ghr,the file is %s,the memorydict is %s ' % (file_obj,len(dict_obj)))
    if len(dict_obj) > 0:
        return '\n'.join(dict_obj)
    else:
        try:
            with open(file_obj,'r') as f:
                tmp_dict_obj = json.load(f)
                if tmp_dict_obj:
                    return '\n'.join(tmp_dict_obj)
        except Exception as err:
            logger.error(err)
        return ""
def deal_common_bsp_cmd(request, obj_list, f_file,bean):
    params_dict = request.body
    logger.info('new api put %s, the content is %s ' % (f_file,params_dict))
    if params_dict:
        tmp_list = []
        json_dict = json.loads(params_dict)
    #    json_dict = json.loads(params_dict.get('body'))
        if json_dict != None and len(json_dict) == 0:
            logger.error('bsp empty command...'+params_dict)
            os.rename(f_file,f_file+'.bak') 
            del obj_list[:]
        for v in json_dict:
            tmp_list.append(bean().gen_obj(v).toString())
        #    tmp_list.append(bean().gen_obj(v))
        if len(tmp_list) > 0:
            del obj_list[:]
            obj_list.extend(tmp_list)
            logger.info("success insert into %s" % f_file+json.dumps(obj_list))
    with open(f_file,'w') as f:
        json.dump(obj_list,f)

def deal_adjust_bsp_cmd(request,f_file,bean,cmd):
    params_dict = request.body
    logger.info('new api put adjust, the content is %s ,the cmd is %s ' % (params_dict,cmd))
    if params_dict:
        params_dict = json.loads(params_dict)
        global adjust_dict
        try:
            with open(f_file,"r") as f:
                adjust_dict_f = json.load(f)
                adjust_dict = {k:bean().gen_obj(v) for k,v in adjust_dict_f.items()}
        except Exception as err:
            logger.error(err)
        for v in params_dict:
            k = "{}={}={}".format(v['domain'],v['node_name'],v['adjust_type'])
            logger.info(k)
            if cmd == "add":
             #   obj_list[k] = bean().gen_obj(v)
                adjust_dict[k] = bean().gen_obj(v)
                logger.info('success to insert..'+str(k))
            else:
                if adjust_dict.get(k) != None:
                    del adjust_dict[k]
                    logger.info('success to in dict del..'+str(k))
        with open(f_file,'w') as f:
            json.dump(adjust_dict,f,default=serialize_instance)
	    return "success"
    else:
	    return ""
def deal_old_bsp_cmd(params_dict, obj_list, f_file,bean):
    logger.info('old api put old content , the content is %s ' % params_dict)
    
    if params_dict.get('adjust_body'):
        tmp_list = []
        json_dict = json.loads(params_dict.get('adjust_body'))
        if json_dict != None and len(json_dict) == 0:
            logger.error('bsp empty command...'+params_dict.get('adjust_body'))
            os.rename(f_file,f_file+'.bak') 
            del obj_list[:]
        for v in json_dict:
            tmp_list.append(bean().gen_ori_obj(v))
        if len(tmp_list) > 0:
            del obj_list[:]
            obj_list.extend(tmp_list)
    with open(f_file ,'w') as f:
        for obj in obj_list:
            f.write(obj.toOriString())
            f.write('\n')
def readfile(request, response_head, obj_list, f_file):
    logger.debug('old api get bsp or ghr,the file is %s,the memorydict is %s ' % (f_file,json.dumps(obj_list,default=serialize_instance)))
    tmp_body = []
    if obj_list != None and len(obj_list) > 0:
        for obj in obj_list:
            tmp_body.append(obj.toOriString())
        return "\n".join(tmp_body)
    else:
        if os.path.isfile(f_file):
            content = open(f_file,'r').read()
            return content
        return ""

