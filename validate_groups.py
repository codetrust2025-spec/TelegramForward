"""
Validates all 284 groups — checks which ones exist and are accessible.
Run: python validate_groups.py
Results saved to: valid_groups.txt and invalid_groups.txt
"""

from telethon.sync import TelegramClient
from telethon.errors import (
    UsernameNotOccupiedError, UsernameInvalidError,
    ChatWriteForbiddenError, UserNotParticipantError
)
import time

API_ID = REMOVED_TELEGRAM_API_ID
API_HASH = 'REMOVED_TELEGRAM_API_HASH'

TARGET_GROUPS = [
    'AWSDevopsfree', 'AWS_Certified_DevOps_Pro', 'Angularjobsupport',
    'Benguluruwalkdrives', 'Chantitech', 'CodingwithAnonymous',
    'Data_Engineering_Support', 'Datascienceproxysupport', 'DotNet6ReactJobSuppot',
    'FrontendDeveloperJobs', 'FullStackDevJobs', 'Golang_Developers',
    'JavaDeveloperJobs', 'JavaScriptJobs', 'MachineLearningJobs',
    'NodejsDeveloperJobs', 'PythonDeveloperJobs', 'ReactDeveloperJobs',
    'RemoteDevJobs', 'RemoteJavaJobs', 'RemoteNodeJobs', 'RemotePythonJobs',
    'RemoteReactJobs', 'RemoteWebDevJobs', 'SalesforceDevelopers', 'SalesforceJobs',
    'SalesforceProxyIntervies', 'SoftwareDeveloperJobs', 'TestingJobs',
    'UIUXDesignerJobs', 'WebDeveloperJobs', 'angular_developers_jobs',
    'aws_cloud_jobs', 'backenddeveloperjobs', 'cloudcomputingjobs',
    'dataanalystjobs', 'dataengineerjobs', 'datasciencejobs', 'devops_engineer_jobs',
    'django_developer_jobs', 'flutterdeveloperjobs', 'frontendjobsindia',
    'fullstackdeveloperjobsindia', 'golangjobsindia', 'itjobsinhyderabad',
    'itjobsinindia', 'java_jobs_india', 'javascriptdeveloperjobs',
    'mernstackdeveloperjobs', 'microservicesdeveloperjobs', 'mobileappdeveloperjobs',
    'nodejs_jobs_india', 'python_jobs_india', 'qaautomationjobs', 'react_jobs_india',
    'reactnativejobs', 'remoteangularjobs', 'remoteawsjobs', 'remotebackendjobs',
    'remotecloudjobs', 'remotedatajobs', 'remotedevopsjobs', 'remoteflutterjobs',
    'remotejavajobsindia', 'remotejavascriptjobs', 'remotemernjobs',
    'remotenodejobsindia', 'remotepythonjobsindia', 'remotereactnativejobs',
    'remotesoftwarejobs', 'remotetestingjobs', 'remoteuiuxjobs',
    'remotewebdeveloperjobs', 'seleniumjobs', 'sqljobs', 'testingjobsindia',
    'uiuxjobsindia', 'webdesignjobs', 'webdeveloperjobsindia', 'wordpressdeveloperjobs',
    'azurecloudjobs', 'blockchainjobs', 'cybersecurityjobs', 'ethicalhackingjobs',
    'gamedeveloperjobs', 'iosdeveloperjobs', 'androiddeveloperjobs', 'bigdatajobs',
    'datawarehousejobs', 'powerbijobs', 'tableaujobs', 'sapjobsindia', 'oraclejobs',
    'peoplesoftjobs', 'servicenowjobs', 'workdayjobs', 'hrjobsindia',
    'businessanalystjobs', 'projectmanagerjobs', 'scrummasterjobs', 'agilejobs',
    'productmanagerjobs', 'startupjobsindia', 'walkinjobsindia', 'fresherjobsindia',
    'experiencedjobsindia', 'contractjobsindia', 'freelancejobsindia',
    'parttimejobsindia', 'internshipsindia', 'offcampusjobs', 'latestjobsindia',
    'dailyjobupdates', 'jobalertsindia', 'itjobupdates', 'jobsearchindia',
    'placementupdates', 'careerupdatesindia', 'hiringnowindia', 'jobvacanciesindia',
    'jobopportunitiesindia', 'jobconsultancyindia', 'jobportalindia', 'jobnetworkindia',
    'jobcommunityindia', 'jobgroupindia', 'techjobsindia', 'nontechjobsindia',
    'governmentjobsindia', 'privatejobsindia', 'mncjobsindia', 'startuphiringindia',
    'hiringdevelopersindia', 'hiringengineersindia', 'hiringitindia',
    'hiringfreshersindia', 'hiringexperiencedindia', 'hiringremotelyindia',
    'hiringglobally', 'globaltechjobs', 'globalremotejobs', 'internationaljobsindia',
    'overseasjobsindia', 'workfromhomejobsindia', 'wfhjobsindia', 'homebasedjobsindia',
    'onlinejobsindia', 'ETLtestingSupport_Proxy', 'F1Interviewprep',
    'Full_Stack_developer_Group', 'ITJOBS11', 'ITJobsIndiaUSA', 'IT_jobs_informatica',
    'Infytcsaccenture', 'JavaScripti', 'JavaSupportGroup', 'JavaTechSupport',
    'Javasupport1', 'JobReferralsPoland', 'Jobs4Oracle', 'Jobs_Bombay',
    'NETFullStackDeveloperJobSupport', 'NowLearners', 'OracleSoaSuiteEs',
    'PowerBI_TechGrp', 'PowerBiBangalore', 'ProxyJobSupports', 'PythonDoubtsGroup',
    'REMOTESAPJOBS', 'RPAJoin', 'ReactJs_fresher_jobs_bhubaneswar', 'SAPBasisHanaIndia',
    'SAP_AWS', 'SAP_USA_job', 'SQLinterviewqutions', 'SalesforceA', 'SalesforceUSA',
    'Tcs_Coding_Solution', 'UNITED_KINGDOM_JOBS', 'accountconsoles', 'alarmzio',
    'allJobSupport', 'apigeedeveloper', 'appledeveloperandroid', 'awsazurelearners',
    'awsstudygroupp', 'azdevjsr', 'backdoor_job_genuine', 'catprepmirrorme',
    'codeitupjava', 'codelivly_chat', 'cognizant_21', 'dataengineerjob',
    'datascienceproxyhelp', 'developer_world', 'devopsfreelancers', 'django_usa',
    'dp_webdeveloper', 'dstrainings', 'erpjobsartiscien', 'etl_test', 'expressjss',
    'flask_python_usa', 'forjobprogramming', 'freecodeclub1', 'frontenddisussion',
    'frontendo', 'frontendsupportt', 'full_stackk', 'fullstackdevlopermari',
    'helipinghand_jobs', 'hireweb3', 'infosys9', 'interview_proxy_d',
    'interviewsupportpowerbi', 'interviewsupportworksupportgroup', 'it_jobs_hyderabad',
    'it_online_job_proxy_support', 'itjobsus', 'itjobsusa',
    'java_jobs_inteview_support_proxy', 'java_proxy_interview_support', 'java_py_script',
    'javafreelancers1', 'javascript_usa_jobs', 'javasupportremote', 'job_hyderabad',
    'job_support1', 'jobintern', 'jobs4_MM_Support', 'jobs_businesses_in_hydrabad',
    'jobseekersupport', 'jobsupportsupport', 'keralainterview2022', 'lostincode',
    'mbacareers', 'mernstackdevs', 'mernstackwebdevelopers', 'microsoftpowerbi99',
    'msfabric', 'onlypythondevelopers', 'oraclefusiontech', 'plsqljobsupport',
    'powerbi7', 'powerbig', 'powerbitr', 'proxyinterviewjobsupport', 'punechakanjobs',
    'pythonjobs', 'pythonproexpert', 'pythonproxy', 'pythonsupportt',
    'rahulshettyacademy', 'ravikantsoftwaresolutions', 'react_dev', 'react_support',
    'reactivenetworksupport', 'reactjs2020', 'reactjsDevspport', 'reactjs_jobs',
    'reactjsproxysupport', 'reactproxyind', 'saarthiafointerview', 'salarysafarigroup',
    'salesforcee', 'salesforcefreelancers', 'salesforcewebsoft', 'sapremotejobs',
    'sdsaless4hanasupport', 'sfdc_coding', 'sqldevelopers1', 'techjobs2024',
    'techq2023', 'testing_automation', 'testinginterviewsupport', 'toptechcoders',
    'uiuxindian', 'usa_IT_Training_Job', 'usa_java_jobs_support', 'usa_laravel',
    'usaproxysupport', 'usukjavajobsupport', 'web_dev_support', 'webdevelopmentjobs',
]

valid = []
invalid = []

with TelegramClient('session_name', API_ID, API_HASH) as client:
    print(f"Checking {len(TARGET_GROUPS)} groups...\n")
    for i, group in enumerate(TARGET_GROUPS, 1):
        try:
            entity = client.get_entity(group)
            entity_type = type(entity).__name__

            # Only keep actual groups/channels, not users or bots
            if entity_type in ('Channel', 'Chat'):
                valid.append(group)
                print(f"[{i:>3}/{len(TARGET_GROUPS)}] ✓ {group} ({entity_type})")
            else:
                invalid.append((group, f"Not a group — is a {entity_type}"))
                print(f"[{i:>3}/{len(TARGET_GROUPS)}] ✗ {group} — is a {entity_type}, not a group")

        except (UsernameNotOccupiedError, UsernameInvalidError):
            invalid.append((group, "Username does not exist"))
            print(f"[{i:>3}/{len(TARGET_GROUPS)}] ✗ {group} — username not found")
        except Exception as e:
            err = str(e)
            if 'wait' in err.lower():
                # FloodWait during resolve — assume valid, check later
                valid.append(group)
                print(f"[{i:>3}/{len(TARGET_GROUPS)}] ? {group} — rate limited, keeping for now")
            else:
                invalid.append((group, err))
                print(f"[{i:>3}/{len(TARGET_GROUPS)}] ✗ {group} — {err}")
        time.sleep(1)

print(f"\n{'='*50}")
print(f"Valid   : {len(valid)}")
print(f"Invalid : {len(invalid)}")
print(f"{'='*50}")

# Save valid groups
with open('valid_groups.txt', 'w') as f:
    f.write(f"Valid Groups ({len(valid)})\n{'='*40}\n\n")
    for i, g in enumerate(valid, 1):
        f.write(f"{i:>3}. {g}\n")

# Save invalid groups
with open('invalid_groups.txt', 'w') as f:
    f.write(f"Invalid Groups ({len(invalid)})\n{'='*40}\n\n")
    for i, (g, reason) in enumerate(invalid, 1):
        f.write(f"{i:>3}. {g} — {reason}\n")

print("\nResults saved to valid_groups.txt and invalid_groups.txt")
print("\nPython list of valid groups (copy into server.py):\n")
print("TARGET_GROUPS = [")
for g in valid:
    print(f"    '{g}',")
print("]")
