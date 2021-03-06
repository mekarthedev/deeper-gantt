#!/usr/bin/python

import base64
import json
import urllib
import urlparse
import httplib

class JIRA:
    def __init__(self, endpoint, username=None, password=None):
        self.endpoint = endpoint
        self.username = username
        self.password = password

    def search(self, jql, offset=None, limit=None, fields=None, expand=None):
        return self.callJiraAPI("GET", "/rest/api/2/search?"
                                + "jql=" + urllib.quote(jql)
                                + ("&fields={0}".format(urllib.quote(','.join(fields))) if fields else "")
                                + ("&expand={0}".format(urllib.quote(','.join(expand))) if expand else "")
                                + ("&startAt={0}".format(offset) if offset else "")
                                + ("&maxResults={0}".format(limit) if limit else ""))

    def getFields(self):
        return self.callJiraAPI("GET", "/rest/api/2/field")

    def getCommits(self, issueId):
        return self.callJiraAPI("GET", "/rest/dev-status/1.0/issue/detail?"
                                + "issueId=" + urllib.quote(issueId)
                                + "&applicationType=stash&dataType=repository"
                                )["detail"][0]["repositories"]

    def callJiraAPI(self, method, resource, body=None):
        authHeader = base64.b64encode(self.username + ":" + self.password) if self.username else None
        statusCode, data = self.callAPI(self.endpoint, method, resource, body, authHeader)
        return data

    def callAPI(self, endpoint, method, resource, body=None, authHeader=None):
        headers = {}
        bodyData = None
        if body is not None:
            bodyData = json.dumps(body)
            headers["Content-Type"] = "application/json"
            
        if authHeader is not None:
            headers["Authorization"] = "Basic " + authHeader

        endp = urlparse.urlparse(endpoint)
        if not endp.netloc:
            endp = urlparse.urlparse("//" + endpoint)

        MakeConnection = httplib.HTTPSConnection
        if 'http' == endp.scheme:
            MakeConnection = httplib.HTTPConnection
        connection = MakeConnection(endp.netloc, timeout=10)

        connection.request(method, resource, bodyData, headers)
        response = connection.getresponse()
        statusCode, data = response.status, response.read()
        connection.close()
        
        return statusCode, json.loads(data)
