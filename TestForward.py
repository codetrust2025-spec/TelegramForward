from telethon import TelegramClient
from telethon.errors import FloodWaitError, ChatWriteForbiddenError, UserBannedInChannelError, UsernameNotOccupiedError, UsernameInvalidError
from telethon.tl.patched import MessageService
import asyncio

api_id = 30631910
api_hash = '17300a40e543c6ac81d6dc2f6119a2cc'

client = TelegramClient('session_name', api_id, api_hash)

# SOURCE GROUP
source_chat = 'forwardmessage123'

# TARGET GROUPS (same list as Forward.py)
target_groups = [
    # --- Original groups ---
    'AWSDevopsfree',
    'AWS_Certified_DevOps_Pro',
    'Angularjobsupport',
    'Benguluruwalkdrives',
    'Chantitech',
    'CodingwithAnonymous',
    'Data_Engineering_Support',
    'Datascienceproxysupport',
    'DotNet6ReactJobSuppot',
    'FrontendDeveloperJobs',
    'FullStackDevJobs',
    'Golang_Developers',
    'JavaDeveloperJobs',
    'JavaScriptJobs',
    'MachineLearningJobs',
    'NodejsDeveloperJobs',
    'PythonDeveloperJobs',
    'ReactDeveloperJobs',
    'RemoteDevJobs',
    'RemoteJavaJobs',
    'RemoteNodeJobs',
    'RemotePythonJobs',
    'RemoteReactJobs',
    'RemoteWebDevJobs',
    'SalesforceDevelopers',
    'SalesforceJobs',
    'SalesforceProxyIntervies',
    'SoftwareDeveloperJobs',
    'TestingJobs',
    'UIUXDesignerJobs',
    'WebDeveloperJobs',
    'angular_developers_jobs',
    'aws_cloud_jobs',
    'backenddeveloperjobs',
    'cloudcomputingjobs',
    'dataanalystjobs',
    'dataengineerjobs',
    'datasciencejobs',
    'devops_engineer_jobs',
    'django_developer_jobs',
    'flutterdeveloperjobs',
    'frontendjobsindia',
    'fullstackdeveloperjobsindia',
    'golangjobsindia',
    'itjobsinhyderabad',
    'itjobsinindia',
    'java_jobs_india',
    'javascriptdeveloperjobs',
    'mernstackdeveloperjobs',
    'microservicesdeveloperjobs',
    'mobileappdeveloperjobs',
    'nodejs_jobs_india',
    'python_jobs_india',
    'qaautomationjobs',
    'react_jobs_india',
    'reactnativejobs',
    'remoteangularjobs',
    'remoteawsjobs',
    'remotebackendjobs',
    'remotecloudjobs',
    'remotedatajobs',
    'remotedevopsjobs',
    'remoteflutterjobs',
    'remotejavajobsindia',
    'remotejavascriptjobs',
    'remotemernjobs',
    'remotenodejobsindia',
    'remotepythonjobsindia',
    'remotereactnativejobs',
    'remotesoftwarejobs',
    'remotetestingjobs',
    'remoteuiuxjobs',
    'remotewebdeveloperjobs',
    'seleniumjobs',
    'sqljobs',
    'testingjobsindia',
    'uiuxjobsindia',
    'webdesignjobs',
    'webdeveloperjobsindia',
    'wordpressdeveloperjobs',
    'azurecloudjobs',
    'blockchainjobs',
    'cybersecurityjobs',
    'ethicalhackingjobs',
    'gamedeveloperjobs',
    'iosdeveloperjobs',
    'androiddeveloperjobs',
    'bigdatajobs',
    'datawarehousejobs',
    'powerbijobs',
    'tableaujobs',
    'sapjobsindia',
    'oraclejobs',
    'peoplesoftjobs',
    'servicenowjobs',
    'workdayjobs',
    'hrjobsindia',
    'businessanalystjobs',
    'projectmanagerjobs',
    'scrummasterjobs',
    'agilejobs',
    'productmanagerjobs',
    'startupjobsindia',
    'walkinjobsindia',
    'fresherjobsindia',
    'experiencedjobsindia',
    'contractjobsindia',
    'freelancejobsindia',
    'parttimejobsindia',
    'internshipsindia',
    'offcampusjobs',
    'latestjobsindia',
    'dailyjobupdates',
    'jobalertsindia',
    'itjobupdates',
    'jobsearchindia',
    'placementupdates',
    'careerupdatesindia',
    'hiringnowindia',
    'jobvacanciesindia',
    'jobopportunitiesindia',
    'jobconsultancyindia',
    'jobportalindia',
    'jobnetworkindia',
    'jobcommunityindia',
    'jobgroupindia',
    'techjobsindia',
    'nontechjobsindia',
    'governmentjobsindia',
    'privatejobsindia',
    'mncjobsindia',
    'startuphiringindia',
    'hiringdevelopersindia',
    'hiringengineersindia',
    'hiringitindia',
    'hiringfreshersindia',
    'hiringexperiencedindia',
    'hiringremotelyindia',
    'hiringglobally',
    'globaltechjobs',
    'globalremotejobs',
    'internationaljobsindia',
    'overseasjobsindia',
    'workfromhomejobsindia',
    'wfhjobsindia',
    'homebasedjobsindia',
    'onlinejobsindia',

    # --- New groups from Excel list ---
    'ETLtestingSupport_Proxy',
    'F1Interviewprep',
    'Full_Stack_developer_Group',
    'ITJOBS11',
    'ITJobsIndiaUSA',
    'IT_jobs_informatica',
    'Infytcsaccenture',
    'JavaScripti',
    'JavaSupportGroup',
    'JavaTechSupport',
    'Javasupport1',
    'JobReferralsPoland',
    'Jobs4Oracle',
    'Jobs_Bombay',
    'NETFullStackDeveloperJobSupport',
    'NowLearners',
    'OracleSoaSuiteEs',
    'PowerBI_TechGrp',
    'PowerBiBangalore',
    'ProxyJobSupports',
    'PythonDoubtsGroup',
    'REMOTESAPJOBS',
    'RPAJoin',
    'ReactJs_fresher_jobs_bhubaneswar',
    'SAPBasisHanaIndia',
    'SAP_AWS',
    'SAP_USA_job',
    'SQLinterviewqutions',
    'SalesforceA',
    'SalesforceUSA',
    'Tcs_Coding_Solution',
    'UNITED_KINGDOM_JOBS',
    'accountconsoles',
    'alarmzio',
    'allJobSupport',
    'apigeedeveloper',
    'appledeveloperandroid',
    'awsazurelearners',
    'awsstudygroupp',
    'azdevjsr',
    'backdoor_job_genuine',
    'catprepmirrorme',
    'codeitupjava',
    'codelivly_chat',
    'cognizant_21',
    'dataengineerjob',
    'datascienceproxyhelp',
    'developer_world',
    'devopsfreelancers',
    'django_usa',
    'dp_webdeveloper',
    'dstrainings',
    'erpjobsartiscien',
    'etl_test',
    'expressjss',
    'flask_python_usa',
    'forjobprogramming',
    'freecodeclub1',
    'frontenddisussion',
    'frontendo',
    'frontendsupportt',
    'full_stackk',
    'fullstackdevlopermari',
    'helipinghand_jobs',
    'hireweb3',
    'infosys9',
    'interview_proxy_d',
    'interviewsupportpowerbi',
    'interviewsupportworksupportgroup',
    'it_jobs_hyderabad',
    'it_online_job_proxy_support',
    'itjobsus',
    'itjobsusa',
    'java_jobs_inteview_support_proxy',
    'java_proxy_interview_support',
    'java_py_script',
    'javafreelancers1',
    'javascript_usa_jobs',
    'javasupportremote',
    'job_hyderabad',
    'job_support1',
    'jobintern',
    'jobs4_MM_Support',
    'jobs_businesses_in_hydrabad',
    'jobseekersupport',
    'jobsupportsupport',
    'keralainterview2022',
    'lostincode',
    'mbacareers',
    'mernstackdevs',
    'mernstackwebdevelopers',
    'microsoftpowerbi99',
    'msfabric',
    'onlypythondevelopers',
    'oraclefusiontech',
    'plsqljobsupport',
    'powerbi7',
    'powerbig',
    'powerbitr',
    'proxyinterviewjobsupport',
    'punechakanjobs',
    'pythonjobs',
    'pythonproexpert',
    'pythonproxy',
    'pythonsupportt',
    'rahulshettyacademy',
    'ravikantsoftwaresolutions',
    'react_dev',
    'react_support',
    'reactivenetworksupport',
    'reactjs2020',
    'reactjsDevspport',
    'reactjs_jobs',
    'reactjsproxysupport',
    'reactproxyind',
    'saarthiafointerview',
    'salarysafarigroup',
    'salesforcee',
    'salesforcefreelancers',
    'salesforcewebsoft',
    'sapremotejobs',
    'sdsaless4hanasupport',
    'sfdc_coding',
    'sqldevelopers1',
    'techjobs2024',
    'techq2023',
    'testing_automation',
    'testinginterviewsupport',
    'toptechcoders',
    'uiuxindian',
    'usa_IT_Training_Job',
    'usa_java_jobs_support',
    'usa_laravel',
    'usaproxysupport',
    'usukjavajobsupport',
    'web_dev_support',
    'webdevelopmentjobs',
]


async def main():
    await client.start()
    print("Test Mode — Sending latest message once to all groups...\n")

    # Fetch the single latest non-service message
    messages = await client.get_messages(source_chat, limit=10)
    messages = [m for m in messages if not isinstance(m, MessageService)]

    if not messages:
        print("No forwardable messages found in source group.")
        return

    msg = messages[0]  # latest message
    print(f"Forwarding Message ID: {msg.id}\n")

    success_groups = []
    failed_groups = []

    for group in target_groups:
        while True:
            try:
                await client.forward_messages(group, msg)
                print(f"  ✓ Forwarded to {group}")
                success_groups.append(group)
                await asyncio.sleep(3)
                break

            except FloodWaitError as e:
                print(f"  ⚠ FloodWait for {group}: waiting {e.seconds}s...")
                await asyncio.sleep(e.seconds + 5)

            except (ChatWriteForbiddenError, UserBannedInChannelError,
                    UsernameNotOccupiedError, UsernameInvalidError) as e:
                print(f"  ✗ Skipping {group}: {e}")
                failed_groups.append(group)
                break

            except Exception as e:
                err = str(e).lower()
                if 'username' in err or 'nobody is using' in err or 'unacceptable' in err:
                    print(f"  ✗ Skipping {group} (invalid username): {e}")
                else:
                    print(f"  ✗ Error in {group}: {e}")
                failed_groups.append(group)
                break

    # Final summary
    print(f"\n{'─' * 40}")
    print(f"  TEST COMPLETE — Summary")
    print(f"{'─' * 40}")
    print(f"  ✓ Success : {len(success_groups):>4} groups")
    print(f"  ✗ Failed  : {len(failed_groups):>4} groups")
    if failed_groups:
        print(f"\n  Failed groups:")
        for g in failed_groups:
            print(f"    - {g}")
    print(f"{'─' * 40}")


with client:
    client.loop.run_until_complete(main())
