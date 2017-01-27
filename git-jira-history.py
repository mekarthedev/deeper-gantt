#!/usr/bin/python

import jira
import json
import sys
import urlparse
import pytz
import datetime
import dateutil.parser
from optparse import OptionParser
import unittest

DEBUG = False

def logDebug(msg):
    if DEBUG:
        for line in msg.split('\n'):
            sys.stderr.write("[DEBUG] " + line + "\n")

def printIssues(issues, reachables):
    reachablesJSON = []
    for key, rev, repo in reachables:
        issue = [i for i in issues if i['key'] == key][0]
        reachablesJSON.append({
            'key': key,
            'endpoint': jiraEndpoint,
            'summary': issue['fields']['summary'],
            'resolution': issue['fields']['resolution']['name'],
            'revision': rev,
            'repository': repo})
    print json.dumps(reachablesJSON)

def resolveEndpointAddress(endpoint):
    endp = urlparse.urlparse(endpoint)
    if not endp.netloc:  # simple host definition will be interpreted as path, not as host name
        endpoint = '//' + endpoint
    if not endp.scheme:
        endpoint = 'https:' + endpoint
    return endpoint

def parseUserCredentials(credentialsString):
    credentials = credentialsString.split(":", 1)
    return (credentials[0], credentials[1] if len(credentials) > 1 else None)

def buildHistoryChart(client, query):
    chart = []

    issues = client.search(query, fields=["timeestimate", "created"], expand=["changelog"])
    for issue in issues["issues"]:
        chartEntry = {}

        chartIssue = {
            "key": issue["key"],
            "created": issue["fields"]["created"],
        }
        chartEntry["issue"] = chartIssue

        # timings

        for update in issue["changelog"]["histories"]:
            for entry in update["items"]:
                if entry.get("toString") == "In Progress":
                    chartIssue["started"] = update["created"]
                if entry.get("toString") == "Resolved":
                    chartIssue["completed"] = update["created"]

        if chartIssue.get("started"):
            estimatedDuration = issue["fields"]["timeestimate"]
            chartIssue["estimate"] = estimatedDuration

            if issue["fields"].get("timeestimate"):
                startedDate = dateutil.parser.parse(chartIssue.get("started"))
                estimatedEndDate = startedDate + datetime.timedelta(seconds=estimatedDuration)
                chartIssue["estimatedCompletion"] = estimatedEndDate.strftime('%Y-%m-%dT%H:%M:%S.%f%z')

        # commits

        commits = [commit for repository in client.getCommits(issue["id"]) for commit in repository["commits"]]
        chartEntry["commits"] = commits

        # responsible resource

        assignee = None
        for update in issue["changelog"]["histories"]:
            for entry in update["items"]:
                if entry.get("toString") == "In Progress":
                    assignee = update["author"]["name"]

        committers = [commit["author"]["name"] for commit in commits]
        committer = max(set(committers), key=committers.count)

        if committer or assignee:
            chartEntry["resource"] = committer or assignee

        chart.append(chartEntry)

    return sorted(chart, key=lambda x: x["issue"].get("started"))

class Tests(unittest.TestCase):
    def test_parseUserCredentials(self):
        self.assertEqual(parseUserCredentials("user:password"), ("user", "password"))
        self.assertEqual(parseUserCredentials("user"), ("user", None))
        self.assertEqual(parseUserCredentials("user:"), ("user", ""))
        self.assertEqual(parseUserCredentials("user:password:xxx"), ("user", "password:xxx"))

    def test_resolveEndpointAddress(self):
        self.assertEqual(resolveEndpointAddress("jira.com"), "https://jira.com")
        self.assertEqual(resolveEndpointAddress("http://jira.com"), "http://jira.com")
        self.assertEqual(resolveEndpointAddress("https://jira.com/path"), "https://jira.com/path")

    def test_WorkingHours_addWorkTime(self):
        workHours = WorkingHours(dayLength=28800, dayEnd=64800)

        self.assertEqual(
            workHours.addWorkTime(dateutil.parser.parse("2017-01-01T12:00:00"), datetime.timedelta(hours=4)),
            dateutil.parser.parse("2017-01-01T16:00:00")
        )
        self.assertEqual(
            workHours.addWorkTime(dateutil.parser.parse("2017-01-01T16:00:00"), datetime.timedelta(hours=3)),
            dateutil.parser.parse("2017-01-02T11:00:00")
        )
        self.assertEqual(
            workHours.addWorkTime(dateutil.parser.parse("2017-01-01T12:00:00"), datetime.timedelta(hours=8)),
            dateutil.parser.parse("2017-01-02T12:00:00")
        )
        self.assertEqual(
            workHours.addWorkTime(dateutil.parser.parse("2017-01-01T00:00:00"), datetime.timedelta(hours=8)),
            dateutil.parser.parse("2017-01-01T18:00:00")
        )

    def test_buildHistoryChart(self):
        class MockJira:
            def search(self, jql, offset=None, limit=None, fields=None, expand=None):
                return {
                    # The second issue was created later than the first. But the second issue was started earlier.
                    "issues": [
                        {
                            "id": "1234",
                            "key": "TEST-1",
                            "fields": {
                                "timeestimate": 28800,
                                "created": "2017-01-01T00:00:01.000+0000",
                            },
                            "changelog": {
                                "histories": [
                                    {
                                        "created": "2017-01-04T00:00:01.000+0000",
                                        "author": {
                                            "name": "developer2",
                                        },
                                        "items": [
                                            {
                                                "field": "status",
                                                "fromString": "Open",
                                                "toString": "In Progress"
                                            }
                                        ]
                                    },
                                    {
                                        "created": "2017-01-04T01:00:01.000+0000",
                                        "author": {
                                            "name": "developer2",
                                        },
                                        "items": [
                                            {
                                                "field": "status",
                                                "fromString": "In Progress",
                                                "toString": "In Review"
                                            }
                                        ]
                                    },
                                    {
                                        "created": "2017-01-04T02:00:01.000+0000",
                                        "author": {
                                            "name": "developer1",
                                        },
                                        "items": [
                                            {
                                                "field": "status",
                                                "fromString": "In Review",
                                                "toString": "Resolved"
                                            }
                                        ]
                                    },
                                    {
                                        "created": "2017-01-04T03:00:01.000+0000",
                                        "author": {
                                            "name": "tester1",
                                        },
                                        "items": [
                                            {
                                                "field": "status",
                                                "fromString": "Resolved",
                                                "toString": "Closed"
                                            }
                                        ]
                                    },
                                ]
                            }
                        },
                        {
                            "id": "5678",
                            "key": "TEST-2",
                            "fields": {
                                "timeestimate": 28800,
                                "created": "2017-01-02T00:00:01.000+0000",
                            },
                            "changelog": {
                                "histories": [
                                    {
                                        "created": "2017-01-03T00:00:01.000+0000",
                                        "author": {
                                            "name": "developer1",
                                        },
                                        "items": [
                                            {
                                                "field": "status",
                                                "fromString": "Open",
                                                "toString": "In Progress"
                                            }
                                        ]
                                    },
                                    {
                                        "created": "2017-01-03T01:00:01.000+0000",
                                        "author": {
                                            "name": "developer1",
                                        },
                                        "items": [
                                            {
                                                "field": "status",
                                                "fromString": "In Progress",
                                                "toString": "In Review"
                                            }
                                        ]
                                    },
                                    {
                                        "created": "2017-01-03T02:00:01.000+0000",
                                        "author": {
                                            "name": "developer2",
                                        },
                                        "items": [
                                            {
                                                "field": "status",
                                                "fromString": "In Review",
                                                "toString": "Resolved"
                                            }
                                        ]
                                    },
                                    {
                                        "created": "2017-01-03T03:00:01.000+0000",
                                        "author": {
                                            "name": "tester1",
                                        },
                                        "items": [
                                            {
                                                "field": "status",
                                                "fromString": "Resolved",
                                                "toString": "Closed"
                                            }
                                        ]
                                    },
                                ]
                            }
                        }
                    ]
                }

            def getCommits(self, issueId):
                if issueId == "1234":
                    return [
                        {
                            "url": "https://test.test/test-repo",
                            "commits": [
                                {
                                    "id": "39c6ba96cdfc4ce348ca88a13913a0fde3556f07",
                                    "author": {
                                        "name": "developer2"
                                    },
                                    "authorTimestamp": "2017-01-04T00:50:01.000+0000"
                                }
                            ]
                        }
                    ]

                elif issueId == "5678":
                    return [
                        {
                            "url": "https://test.test/test-repo",
                            "commits": [
                                {
                                    "id": "5c8e9bc64fa00ce304fb65a75b2ab4d30be68436",
                                    "author": {
                                        "name": "developer1"
                                    },
                                    "authorTimestamp": "2017-01-03T00:50:01.000+0000"
                                }
                            ]
                        }
                    ]

                else:
                    return []

        historyChart = buildHistoryChart(MockJira(), "jql = test")
        self.maxDiff = None
        self.assertEqual(historyChart, [
            {
                "resource": "developer1",
                "issue": {
                    "key": "TEST-2",
                    "created": "2017-01-02T00:00:01.000+0000",
                    "estimate": 28800,
                    "estimatedCompletion": "2017-01-04T00:00:01.000+0000",
                    "started": "2017-01-03T00:00:01.000+0000",
                    "completed": "2017-01-03T02:00:01.000+0000",
                },
                "commits": [
                    {
                        "id": "5c8e9bc64fa00ce304fb65a75b2ab4d30be68436",
                        "author": {
                            "name": "developer1"
                        },
                        "authorTimestamp": "2017-01-03T00:50:01.000+0000"
                    }
                ],
            },
            {
                "resource": "developer2",
                "issue": {
                    "key": "TEST-1",
                    "created": "2017-01-01T00:00:01.000+0000",
                    "estimate": 28800,
                    "estimatedCompletion": "2017-01-05T00:00:01.000+0000",
                    "started": "2017-01-04T00:00:01.000+0000",
                    "completed": "2017-01-04T02:00:01.000+0000",
                },
                "commits": [
                    {
                        "id": "39c6ba96cdfc4ce348ca88a13913a0fde3556f07",
                        "author": {
                            "name": "developer2"
                        },
                        "authorTimestamp": "2017-01-04T00:50:01.000+0000"
                    }
                ],
            }
        ])

    # TODO: entries without issues
    # TODO: group subtasks in some way

if __name__ == '__main__':
    opt_parser = OptionParser(usage="%prog [options] JIRA_ENDPOINT JIRA_QUERY [GIT_REPO_PATH]",
                              description="")
    opt_parser.add_option("--user", action="store", default=None, metavar="USER:PWD", help="Login credentials.")
    opt_parser.add_option("--test", action="store_true", default=False,
                          help="Run self-testing & diagnostics.")

    opts, args = opt_parser.parse_args()
    if opts.test:
        suite = unittest.TestLoader().loadTestsFromTestCase(Tests)
        unittest.TextTestRunner(verbosity=2).run(suite)

    elif len(args) >= 2:
        DEBUG = opts.debug

        jiraEndpoint = resolveEndpointAddress(args[0])
        jiraQuery = args[1]

        username, password = parseUserCredentials(opts.user) if opts.user else (None, None)

        jiraClient = jira.JIRA(jiraEndpoint, username, password)
        fields = getFieldIDs(jiraClient, opts.search_in)
        issues = getAllIssues(jiraClient, jiraQuery, set(['summary', 'resolution'] + fields))
        revisions = findRevisionsSpecified(jiraClient, issues, fields)
        gitModules = getGitModules(repoRootPath, opts.revision)
        verifiedRevisions = verifyRevisions(revisions, gitModules)

        reachables = findReachables(verifiedRevisions)
        printIssues(issues, reachables)

    else:
        opt_parser.print_help()
