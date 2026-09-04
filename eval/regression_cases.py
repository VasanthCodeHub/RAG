"""
Permanent regression tests for the 3 real failures logged in
`eval/trace_report.json` on 2026-08-26, so the "1 chunk fallback" rerank bug
(fixed in `rag/rerank.py`) can't silently come back.

`RESUME_CORPUS` is the real 25-chunk resume corpus that was in play when the
failures happened, reconstructed from the trace's `documents_preview` field
(each entry is the real chunk, truncated to 300 chars -- enough to reproduce
the bug and verify the fix without needing the original PDF).
"""

RESUME_CORPUS = [
    "Project  Name:  Swapsi   Technologies:  React  Native,  Expo  Managed  Workflow,  Expo  Router,  "
    "EAS  Build,  TypeScript,   Firebase,   Node.js   (Express),   Firestore,   Stripe   Payments,   "
    "Google   Authentication,   Firebase   Remote   Config,   Firebase   Cloud   Messaging   (FCM),   "
    "React   Na...",
    "RECENT  PROFESSIONAL  EXPERIENCE:     Project  Name:  Job  Space   Technologies:  React  "
    "Native,  Expo  Managed  Workflow,  Expo  Router,  EAS  Build,  TypeScript,   Redux   Toolkit,   "
    "Firebase,   Firebase   Cloud   Messaging   (FCM),   Firebase   Crashlytics,   Firebase   "
    "Remote   Config,   React...",
    "Project  Management  Tool:  JIRA   Description:   ●  Keep  track  of  warranty  expiration  "
    "dates  and  schedule  regular  maintenance  for  your   appliances   and   gadgets. ●  Receive  "
    "reviews  from  trusted  sources  like  friends  and  family  to  make  informed  decisions   "
    "about   products. ●...",
    "communication,   and   third-party   services.  ●  Participated  in  code  reviews,  sprint  "
    "planning,  technical  discussions,  testing,  debugging,   estimation,   and   release   "
    "activities.  ●  Worked  with  cross-functional  teams  to  troubleshoot  production  issues  "
    "and  deliver  reliable...",
    "and   terminated   application   states.  ●  Experience  working  with  Android  and  iOS  "
    "build,  release,  and  deployment  workflows   using   EAS   Build,   GitHub   Actions,   and   "
    "Codemagic.  ●  Experienced  in  debugging  production  issues,  analyzing  application  "
    "crashes,   -Mobile  Devel...",
    "Description   Job  Space  is  a  next-generation  job-seeking  platform  designed  exclusively  "
    "for  Australia  and  New   Zealand.   It   empowers   job   seekers   to   explore   "
    "opportunities   across   sectors,   create   professional   profiles,   and   apply   "
    "seamlessly   to   roles.   ●  Job...",
    "notifications   when   matching   jobs   are   posted.  ●  Performance  Tracking:  Application  "
    "status  updates  and  notifications  keep  job  seekers   informed   throughout   the   hiring   "
    "process.  ●  Remote  Config  Management:  Firebase  Remote  Config  is  used  to  dynamically  "
    "update  app...",
    "resolving  integration  issues,  and  contributing  to  application  stability  improvements.  "
    "●  Experience  implementing  deep  linking,  authentication,  biometric  authentication,   "
    "payment   integrations,   and   third-party   mobile   services.  ●  Good  understanding  of  "
    "Git  workflows,  pul...",
    "Navigation  &  Integration:  React  Navigation,  Expo  Router,  Deep  Linking,  "
    "Authentication,   Biometric   Authentication.    Notifications:  Firebase  Cloud  Messaging  "
    "(FCM),  Apple  Push  Notification  Service  (APNs),   Pushwoosh.    Firebase:  Firebase  "
    "Authentication,  Firestore,  Cloud  Fu...",
    "job   applications,   profile   creation,   and   account   management.  ●  Built  resume  "
    "upload  and  cover  letter  management  features  with  seamless  document   handling   and   "
    "validation.  ●  Integrated  REST  APIs  for  job  listings,  application  submissions,  user  "
    "profiles,  and   noti...",
    "premium   feature   monetization.  ●  Implemented  WebSocket  and  Socket.io  based  real-time  "
    "communication  for  instant   matchmaking   updates,   notifications,   and   user   "
    "interactions.  ●  Implemented  push  notification  workflows  using  Firebase  Cloud  Messaging  "
    "(FCM)  and  APNs   for...",
    "●  Push  Notifications:  Implemented  Firebase  Cloud  Messaging  (FCM)  to  notify  users  "
    "about   matches,   swap   requests,   listing   expirations,   and   completed   swaps.  ●  "
    "CI/CD  Integration:  Automated  testing  and  build  generation  using  Codemagic  and  GitHub   "
    "Actions   for   eff...",
    "activities.  ●  Collaborated  with  cross-functional  teams  to  troubleshoot  production  "
    "issues,  enhance   UI/UX,   and   deliver   high-quality   mobile   experiences.  ●  Followed  "
    "Agile  methodologies,  participated  in  sprint  planning,  code  reviews,  and  release   "
    "management   using   Az...",
    "after   which   a   leaderboard   of   mutual   matches   is   generated   for   swap   "
    "selection.  ●  Priority-Based  Swap  Decisions:  The  user  who  listed  first  gets  the  "
    "first  choice  to  finalize  a   swap   from   their   leaderboard,   ensuring   fair   and   "
    "structured   match   resolu...",
    "schedules   to   stay   organized. ●  Access  a  comprehensive  database  of  user  experiences  "
    "and  feedback  on  various  products   and   services   to   make   informed   choices.  "
    "Responsibilities:   ●  Integrated  DigiLocker  to  enable  safe  and  secure  document  "
    "management.  ●  Implemente...",
    "Communication.    Performance:  State  Management  Optimization,  API  Caching,  Pagination,  "
    "Lazy  Loading,   UI   Optimization,   Animation   Optimization.     -Mobile  Developer",
    "and   scalable   development   practices.  ●  Used  React  Hooks,  component  lifecycle  "
    "patterns,  Redux  Toolkit,  and  Context  API  to   manage   application   state   and   user   "
    "interactions.  ●  Designed  and  maintained  navigation  flows  using  React  Navigation  and  "
    "Expo  Router,   incl...",
    "optimized   data   loading   strategies.  ●  Implemented  smooth  animations  and  "
    "gesture-based  interactions  using  React  Native   Reanimated   while   maintaining   "
    "responsive   UI   behavior.  ●  Investigated  application  issues  through  debugging,  crash  "
    "reports,  logs,  and  production...",
    "attention   to   application   performance,   maintainability,   and   consistent   behavior   "
    "across   platforms.  ●  Experience  improving  application  responsiveness  through  optimized  "
    "state   management,   API   caching,   pagination,   lazy   loading,   and   efficient   UI   "
    "rendering.  ●...",
    "Midhun  T   Mobile   Developer           SUMMARY :      ●  4+  years  of  experience  in  "
    "Mobile  development,  primarily  using  React  Native  and   TypeScript,   with   experience   "
    "across   application   development,   testing,   debugging,   maintenance,   and   production   "
    "support.  ●  Strong...",
    "●  Integrated  Firebase  Cloud  Messaging  (FCM)  and  APNs  for  notification  workflows  "
    "across   foreground,   background,   and   terminated   application   states.  ●  Configured  "
    "and  maintained  EAS  Build  workflows  for  Android  and  iOS  application  builds,   "
    "testing,   and   release   g...",
    "tracking.    ●  Implemented  push  notification  workflows  using  Firebase  Cloud  Messaging  "
    "(FCM)  and   APNs   for   warranty   reminders,   maintenance   alerts,   and   user   "
    "engagement   updates.   -Mobile  Developer",
    "●  Developed  job  alert  functionality  with  Firebase  Cloud  Messaging  (FCM)  push  "
    "notifications   for   newly   posted   jobs.  ●  Implemented  Expo  Router  for  navigation  "
    "architecture  and  route  management  across   application   modules.  ●  Configured  and  "
    "maintained  EAS  Build  pipe...",
    "Native   Reanimated   to   enhance   user   engagement   and   application   performance.  ●  "
    "Real-Time  Backend  with  Firebase  &  Socket.io:  Used  Firestore  and  Socket.io  for   "
    "real-time   syncing   of   listings,   matches,   notifications,   and   swap   activities.  ●  "
    "Remote  Config  &  D...",
    "application   states.  ●  Optimized  application  performance  through  efficient  state  "
    "management  using  Redux   Toolkit,   API   caching,   pagination,   and   lazy   loading   "
    "techniques.  ●  Managed  Firebase  Authentication,  Firestore  security  rules,  and  "
    "role-based  access  control.  ●...",
]

# Each case pins one real query that previously produced a bad answer
# (see eval/trace_report.json and TRACE_FINDINGS.md for the "before").
# `problem_type` groups cases for the per-problem-type before/after report.
REGRESSION_CASES = [
    {
        "trace_query_id": "bb1743ba",
        "question": "what are the project's this candidate worked?",
        "problem_type": "project_list",
        "should_answer": True,
        # Either project name is a correct answer -- which one lands in the
        # top-3 reranked chunks depends on close cross-encoder scores.
        "expected_keyword": ["Swapsi", "Job Space"],
    },
    {
        "trace_query_id": "73d12427",
        "question": "who is the candidate for this resume?",
        "problem_type": "candidate_identity",
        "should_answer": True,
        # NOTE: this case is a known, still-open gap, not something the
        # rerank_top_k fix alone resolves. The cross-encoder ranks the
        # "Midhun T Mobile Developer" chunk 7th of 25 for this query (verified
        # by direct scoring), so at the default rerank_top_k=3 it still
        # doesn't reach the LLM. The rerank fix is still correct and
        # necessary (top_k=3 docs now genuinely reach generation instead of
        # collapsing to 1), it just isn't sufficient for this specific,
        # identity-style query against a cross-encoder tuned for general
        # search relevance rather than "which chunk names the resume owner".
        "expected_keyword": "Midhun",
    },
    {
        "trace_query_id": "e8990bdf",
        "question": "which technology this project by the way",
        "problem_type": "tech_stack",
        "should_answer": True,
        "expected_keyword": "React Native",
    },
]

# Small hand-labeled set for judge calibration (see
# eval.judges.check_judge_calibration). These are deliberately clear-cut
# so our own "human_*" scores are trustworthy: an obviously good answer, an
# obviously unhelpful refusal, a rambling partial answer, and a confidently
# wrong (hallucinated) answer.
JUDGE_CALIBRATION_SET = [
    {
        "question": "who is the candidate for this resume?",
        "context": "Midhun T Mobile Developer SUMMARY: 4+ years of experience in Mobile development, "
        "primarily using React Native and TypeScript.",
        "answer": "The candidate is Midhun T, a Mobile Developer with 4+ years of experience in "
        "React Native and TypeScript.",
        "human_helpfulness": 5,
        "human_tone": 5,
    },
    {
        "question": "who is the candidate for this resume?",
        "context": "Midhun T Mobile Developer SUMMARY: 4+ years of experience in Mobile development, "
        "primarily using React Native and TypeScript.",
        "answer": "The provided context does not contain any information about a specific resume "
        "or the individual who authored it. Therefore, the candidate's identity cannot be "
        "determined from the text you shared.",
        "human_helpfulness": 1,
        "human_tone": 2,
    },
    {
        "question": "which technology this project by the way",
        "context": "Project Name: Swapsi Technologies: React Native, Expo, Firebase, Node.js (Express).",
        "answer": "Well, it's hard to say for certain, but the project might involve some kind of "
        "mobile framework, and possibly a backend of some sort, among other things that could "
        "be relevant depending on interpretation.",
        "human_helpfulness": 2,
        "human_tone": 3,
    },
    {
        "question": "which technology this project by the way",
        "context": "Project Name: Swapsi Technologies: React Native, Expo, Firebase, Node.js (Express).",
        "answer": "This project is definitely built entirely in Java with a MySQL backend and "
        "deployed on AWS Lambda, based on standard industry practice for apps like this.",
        "human_helpfulness": 1,
        "human_tone": 2,
    },
]
