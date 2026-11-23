"""Fill the final-report template. Writes final-report.tex next to this script."""
from pathlib import Path

HERE = Path(__file__).resolve().parent
TASKS = ["T-REDACT-01", "T-TARX-01", "T-BOOKMARKS-01", "T-ACCOUNTS-01", "T-PASTE-01"]
CONDS = [r"\texttt{unstructured}", r"\texttt{sdd}", r"\texttt{sdd\_clarify}", r"\texttt{sdd\_secure}"]


# Time and effort of finished builds, from each run's metrics.json: (active min, turns, tokens M, share before implement)
TIME = {("T-ACCOUNTS-01", 3): ("65.7 min", "6", "17.2 M", "33\\%"),
        ("T-TARX-01", 1): ("32.6 min", "6", "13.4 M", "48\\%"),
        ("T-REDACT-01", 3): ("63.0 min$^{\\dagger}$", "9", "19.0 M", "55\\%"),
        ("T-PASTE-01", 2): ("56.4 min$^{\\dagger}$", "12", "18.1 M", "42\\%"),
        ("T-BOOKMARKS-01", 0): ("2.3 min", "1", "0.25 M", "--"),
        ("T-ACCOUNTS-01", 2): ("42.0 min$^{\\dagger}$", "11", "13.5 M", "55\\%"),
        ("T-TARX-01", 3): ("44.4 min$^{\\dagger}$", "6", "14.1 M", "44\\%"),
        ("T-REDACT-01", 2): ("50.4 min$^{\\dagger}$", "12", "15.7 M", "46\\%"),
        ("T-PASTE-01", 0): ("9.4 min", "1", "1.82 M", "--"),
        ("T-BOOKMARKS-01", 1): ("23.8 min", "5", "8.2 M", "57\\%"),
        ("T-ACCOUNTS-01", 0): ("4.8 min", "1", "0.39 M", "--"),
        ("T-TARX-01", 0): ("5.7 min", "1", "0.82 M", "--"),
        ("T-REDACT-01", 1): ("40.7 min$^{\\dagger}$", "7", "14.3 M", "44\\%"),
        ("T-PASTE-01", 3): ("48.3 min", "5", "12.0 M", "44\\%"),
        ("T-BOOKMARKS-01", 2): ("36.5 min$^{\\dagger}$", "12", "13.2 M", "56\\%"),
        ("T-ACCOUNTS-01", 1): ("37.3 min", "5", "12.0 M", "41\\%"),
        ("T-TARX-01", 2): ("43.7 min$^{\\dagger}$", "12", "14.4 M", "54\\%"),
        ("T-REDACT-01", 0): ("7.9 min", "1", "1.31 M", "--"),
        ("T-PASTE-01", 1): ("67.9 min$^{\\dagger}$", "11", "28.2 M", "26\\%"),
        ("T-BOOKMARKS-01", 3): ("37.7 min$^{\\dagger}$", "7", "15.0 M", "48\\%")}


def grid(ncols, data=None):
    """Task x condition rows; a cell is empty unless data has it."""
    lines = []
    for i, task in enumerate(TASKS):
        for j, cond in enumerate(CONDS):
            first = r"\texttt{%s}" % task if j == 0 else ""
            cells = (data or {}).get((task, j), [r"\emptycell"] * ncols)
            lines.append("%s & %s & %s \\\\" % (first, cond, " & ".join(cells)))
        if i < len(TASKS) - 1:
            lines.append(r"\midrule")
    return "\n".join(lines)


tex = r"""\documentclass[12pt]{article}

\usepackage[margin=1in]{geometry}
\usepackage{times}
\usepackage{amsmath,amssymb}
\usepackage{booktabs}
\usepackage{longtable}
\usepackage{array}
\usepackage{xcolor}
\usepackage{hyperref}
\usepackage{enumitem}
\usepackage{setspace}
\usepackage{titlesec}
\usepackage{xurl}
\urlstyle{tt}
\emergencystretch=3em

\hypersetup{
    colorlinks=true,
    linkcolor=blue,
    citecolor=blue,
    urlcolor=blue
}

\newcommand{\ph}[1]{\textcolor{red}{[TO FILL: #1]}}
\newcommand{\emptycell}{\textcolor{red}{[EMPTY]}}
\newcommand{\validationstatus}{\textcolor{red}{[VALIDATION NOT YET COMPLETED]}}

\titleformat{\section}{\large\bfseries}{\thesection}{1em}{}
\titleformat{\subsection}{\normalsize\bfseries}{\thesubsection}{1em}{}

\setlength{\parindent}{0pt}
\setlength{\parskip}{6pt}
\onehalfspacing

\begin{document}

% ----------------------------------------------------------------------
% TITLE PAGE
% ----------------------------------------------------------------------
\begin{titlepage}
    \centering
    \vspace*{1.2in}

    {\LARGE\bfseries Evaluating and Extending Spec-Driven Development:\par}
    \vspace{0.25in}
    {\Large An Empirical Study of GitHub Spec Kit for Software Engineering\par}
    \vspace{0.15in}
    {\Large and OpenOwls SD-KDP for Knowledge-Base Production\par}

    \vspace{0.6in}

    {\large Independent Study Final Report\par}

    \vspace{0.8in}

    {\large Varshil Patel\par}
    {\large TUid: 916646801\par}
    {\large MS Computer Science, Temple University\par}

    \vspace{0.5in}

    {\large Faculty Advisor: Professor Alex Pang\par}

    \vspace{0.5in}

    {\large \today\par}

    \vfill
\end{titlepage}

% ----------------------------------------------------------------------
% ABSTRACT
% ----------------------------------------------------------------------
\section*{Abstract}
\addcontentsline{toc}{section}{Abstract}

This report presents an independent study of Spec-Driven Development (SDD) with GitHub Spec Kit, and an extension of the spec-first idea to knowledge-base production with OpenOwls SD-KDP, compared against OpenKB. The software study directs one coding agent (Claude Code, model \texttt{claude-opus-5}) in four ways on five matched Python projects: plain conversational prompting (``vibe coding''), Spec Kit's default workflow, Spec Kit with its clarification step, and Spec Kit with security requirements written into its constitution. Each build is followed by a change request on the agent's own code, so the study covers existing projects as well as new ones. Correctness, intended behaviour and security are scored by 264 hidden test cases that were written, validated and encrypted before any study run. A purpose-built instrument logs agent time, tokens and human turns. The tasks, prompts, measures, decision rules and analysis code were pre-registered. Validation before the first study run showed that the hidden tests separate safe code from common security shortcuts that pass every example the agent can see: on the change requests, reference code passed all 26 security probes and shortcut code passed 12. In a pilot and a practice comparison, the specification phases took 74\% and 82\% of the agent's time, and no specification was revised after it was written.

Across 48 scored runs (25 builds and 23 change requests), functional correctness (tier~A) reached a ceiling in every condition: all four workflows passed 96--100\% of the hidden tests, with no statistically significant difference (Friedman $p = 1.00$). Security (tier~C) was likewise indistinguishable across conditions overall (Friedman $p = 0.25$), although \texttt{sdd\_secure} raised the tier~C pass rate from 70\% to 100\% on T-REDACT-01 and from 83\% to 100\% on T-PASTE-01, the two tasks whose security-relevant behaviour the constitution addresses directly. These gains came at substantial cost: SDD runs consumed 5--10 times the active time, human turns and tokens of unstructured runs (Friedman $p < 0.01$ on all three measures), with specification and planning phases accounting for 26--57\% of the total.

\textbf{Keywords:} Spec-Driven Development, GitHub Spec Kit, large language models, coding agents, software security, pre-registration, empirical software engineering, knowledge-base production, OpenOwls SD-KDP, OpenKB.

% ----------------------------------------------------------------------
% TABLE OF CONTENTS
% ----------------------------------------------------------------------
\newpage
\tableofcontents
\newpage

% ----------------------------------------------------------------------
% 1. INTRODUCTION
% ----------------------------------------------------------------------
\section{Introduction}

Large language models have moved from code-completion assistants to semi-autonomous coding agents. This shift has popularized conversational, prompt-first development, often called ``vibe coding,'' in which a developer describes intent in a chat interface and iterates until the output appears correct. This mode is fast for prototypes but can produce hidden defects, security vulnerabilities, and drift from the actual requirement because the requirement itself is never made explicit or durable.

Spec-Driven Development responds by making the specification, rather than the prompt or the code, the primary artifact of the workflow. GitHub Spec Kit is a widely adopted open-source implementation that provides a command-line tool and agent-facing slash commands---\texttt{constitution}, \texttt{specify}, \texttt{plan}, \texttt{tasks}, and \texttt{implement}---that walk a coding agent through specification, planning, task decomposition, and implementation.

This independent study uses Spec Kit as both the object of study and the instrument for generating comparable data. It then extends the same question---does specifying before generating change the outcome?---to a second domain: the production of a distilled, queryable knowledge base using OpenOwls SD-KDP, compared structurally and qualitatively against OpenKB.

\subsection{Study Structure at a Glance}

The study was organized into four parts:

\begin{itemize}[leftmargin=*]
    \item \textbf{Part I --- Foundations:} literature review and environment setup for both the software and knowledge-base strands.
    \item \textbf{Part II --- Software SDD Study, Design and Data Collection:} pilot and controlled comparison of Spec Kit against unstructured prompting on matched programming tasks.
    \item \textbf{Part III --- Software SDD Study, Analysis:} defect coding, traceability coding, and draft findings for RQ1--RQ4.
    \item \textbf{Part IV --- Extension to Knowledge-Base Production:} building a distilled knowledge base with OpenOwls SD-KDP and comparing that spec-first workflow against OpenKB, addressing RQ5.
\end{itemize}

\subsection{Execution Summary}\label{sec:execution}

\begin{itemize}[leftmargin=*]
    \item \textbf{Weeks 1--2 (Part I).} Literature review started (Section~\ref{sec:lit}); Spec Kit 1.0.6 installed with the Claude Code integration and checked end to end on a toy feature.
    \item \textbf{Weeks 3--4 (Part II, pilot).} Pilot run R001 (17--20 September 2026) took a CSV expense splitter through Spec Kit's full sequence. The logging instrument \texttt{sddlog} was written and tested (57 tests at the time), and the pilot exposed three instrument defects that were fixed before any study data.
    \item \textbf{Weeks 5--7 (Part II, design).} Five study projects with hidden test suites, fixed prompts and product-owner answer sheets were built, and a pre-registration was drafted. A practice comparison on a login page (excluded from the data) exercised the method. The hidden tests for the builds were validated and sealed on 24 October 2026. In Week~7 the design gained a fourth approach (security in the specification), a change request on each build (the existing-project stage), a Java/Quarkus extension, and a run tool that drives every run; the change-request tests were validated and sealed on 31 October 2026.
    \item \textbf{Week 8.} Mechanics checks R002 and R003 confirmed the procedure end to end (Section~\ref{sec:prelim}). The analysis script was written and tested so that it can be frozen with the plan.
    \item \textbf{Weeks 8--10.} The pre-registration was frozen on 4 November 2026 (merge commit \texttt{5a58b4f}, 23:24 UTC) and the hashes of the sealed suites were emailed the same day. Study runs started with R004 that evening. The last study run (R039C) was completed on 22 November 2026.
    \item \textbf{Week 11.} Unsealing, scoring and coding (Part III); Part IV comparison. Sealed suites unsealed and tree hashes verified on 22 November 2026; all 48 runs scored (73 score files); analysis script run; Tables~\ref{tab:builds} and~\ref{tab:change-requests} filled. Traceability coding and Part IV comparison remain open.
\end{itemize}

\textbf{Deviations from the proposal.}

\begin{enumerate}[leftmargin=*]
    \item \textbf{Schedule.} The proposal placed data collection in Weeks 5--7 and analysis in Weeks 8--9. Because the report is due on 5 December 2026, the end of Week 12, the remaining work was replanned: study runs in Weeks 8--10, scoring and coding in Week 11, writing in Week 12, and Part IV in Weeks 9--11 instead of Weeks 12--15.
    \item \textbf{Design scope.} The proposal compared two conditions. The pilot showed that ambiguity was absorbed without questions, so Spec Kit's clarification step became a manipulated condition. A fourth condition, security written into the constitution, tests the strongest claim in the SDD literature. A change request on each build adds existing projects, and a repeated project measures run-to-run variation.
    \item \textbf{Agent integrations.} The proposal planned two agent integrations; the study uses one harness (Claude Code) so that the comparison is between workflows, not between agents.
    \item \textbf{Java extension.} Two Java 21/Quarkus projects were added in Week 7 and registered separately from the Python study. On 14 November, before any Java run, the extension was dropped to meet the 1 December submission date; its cross-stack question is not answered.
    \item \textbf{Operator.} The Python study runs are operated by Claude, the AI assistant that drafted the study materials, in a cloud workspace, choosing only among fixed replies; the author reviews every decision (Section~\ref{sec:procedure}).
\end{enumerate}

\textbf{Deviations during the study runs.}
\begin{itemize}[leftmargin=*]
    \item R004: the operator's workspace restarted during \texttt{implement}; the same agent session was resumed with the pre-registered resume message (gap 2.8 minutes).
    \item R004C: \texttt{implement} stopped at the account's five-hour usage limit and was resumed with the same message after the limit reset; the 43-minute wait is inside its active time and is reported with the run.
    \item R006, R007, R007C and R009 to R011C: sessions were interrupted by the usage limit or a workspace restart and resumed with the same message, hours or days later. Their logged active time includes the wait, so it is recomputed from event timestamps with idle gaps over 10 minutes removed, and marked as recomputed. The run tool was extended so that a run's first phase can also be resumed.
    \item R007C: one question about password hashing got the safety fallback because the operator's keyword helper matched the run tool's own prompt line; under the registered rules it should have got the no-preference reply. The helper was fixed the same day.
    \item R011C: after a workspace restart the operator started the resume of \texttt{clarify} twice, so two copies of the run tool drove the run together through \texttt{plan}. Its integrity check failed, so R011C is excluded and redone once as R019C, the first spare ID, from a fresh copy of R011's finished build (Section~9 of the pre-registration). Both are reported; the R011C cell is scored from R019C. The operator's launch script now refuses to start a run that is already running. The same run exposed a crash in the logging tool on a non-UTF-8 test file, fixed outside the measured code.
    \item R006: in \texttt{plan} the agent listed three decisions ``you should confirm before implementation''. This was classified as a question; the one point the answer sheet covers got its entry, and the run tool cannot add fallbacks to an entry in the same reply, so the two other points got no reply. The author reviews the classification.
    \item Claude Code version: registered as 2.1.317, but the operator's workspace updated the command-line tool between restarts, so R004--R006 ran on 2.1.318, R006C--R007 on 2.1.321, R007C--R010C on 2.1.322, R011 and R011C on 2.1.323, and R019C on 2.1.325. The model string, Spec Kit and Python did not change. The drift was found in the validation pass of 14 November; from R012 every new run uses a pinned copy of 2.1.317 with automatic updates off. Version is confounded with run order, which counterbalancing spreads across conditions; results by version group are reported as exploratory.
\end{itemize}

% ----------------------------------------------------------------------
% 2. PROBLEM STATEMENT AND MOTIVATION
% ----------------------------------------------------------------------
\section{Problem Statement and Motivation}

Industry claims about SDD's benefits are compelling but unevenly substantiated. Some preprints report large effect sizes, including reductions in security-defect rates and time-to-market. However, these figures often come from single case studies or vendor-adjacent reports rather than replicated, independently designed experiments. At the same time, peer-reviewed work on LLM code generation has established that unconstrained AI-generated code contains security vulnerabilities at meaningful rates.

There is therefore a gap between the strength of claims circulating about spec-driven workflows and the amount of independently reproduced, methodologically transparent evidence behind those claims. A modest, well-scoped independent study cannot resolve this gap at scale, but it can produce a small, honestly reported data point and demonstrate competence in empirical software engineering methods.

The reviewed evidence is narrower than the claims built on it. The 73\% reduction in security defects reported for constitutional SDD comes from one case study~\cite{marri}. The two strongest controlled results state their security constraints explicitly in the specification~\cite{dhuri,grynets}, and the largest observational study of SDD repositories includes no non-SDD repositories~\cite{epic}. The evidence is also not uniformly positive: in a repeated-run study of structured specifications, results varied widely with the system and model, and one specification format lowered the average test pass rate against a plain natural-language specification~\cite{feng}. No large-scale null result for SDD was found among the sources reviewed. None of the studies reviewed compares a full SDD agent workflow against plain prompting of the same agent when security is left implicit, which is how security usually arises in practice. That comparison, for new and existing projects, at measured cost, is the gap this study addresses.

% ----------------------------------------------------------------------
% 3. RESEARCH QUESTIONS
% ----------------------------------------------------------------------
\section{Research Questions}

This study is organized around one primary and several secondary research questions.

\subsection{Software SDD Study}

\textbf{RQ1 (primary):} Does completing a programming task through Spec Kit's spec-driven workflow (\texttt{constitution} $\rightarrow$ \texttt{spec} $\rightarrow$ \texttt{plan} $\rightarrow$ \texttt{tasks} $\rightarrow$ \texttt{implement}) change functional correctness and defect rate relative to completing the same task through unstructured, conversational prompting with the same underlying model?

\textbf{RQ2:} Does the SDD workflow improve requirement-to-code traceability, and can that traceability be measured objectively?

\textbf{RQ3:} What is the time and effort cost of the SDD workflow relative to unstructured prompting, and how does that cost scale with task complexity?

\textbf{RQ4:} Which parts of the Spec Kit workflow---constitution, specification, planning, task breakdown, and consistency checking---contribute most to any observed differences, versus which are procedural overhead with limited measurable effect?

\subsection{Refinement in the Pre-Registration}

Before any study run, the pre-registration made RQ4 concrete as four sub-questions and added one contrast to RQ1 and RQ3:

\begin{itemize}[leftmargin=*]
    \item \textbf{RQ4a, open requirements:} when a requirement is left open, does the agent ask, or decide for itself? Does Spec Kit's clarification stage change this, and the resulting code?
    \item \textbf{RQ4b, specification evolution:} when implementation reveals a problem, does the agent revise the specification or only the code?
    \item \textbf{RQ4c, principle adherence:} are the constitution's principles visible in the final code?
    \item \textbf{RQ4d, existing projects:} when the agent changes a project it built earlier, with no memory of building it, does the workflow change whether the change is correct and secure, whether the earlier behaviour survives, what the change costs, and whether the specification is updated?
    \item \textbf{Security in the specification:} RQ1 and RQ3 also compare \texttt{sdd\_secure} with \texttt{sdd}: does writing security requirements into the constitution change security, and at what cost?
\end{itemize}

Consistency checking (\texttt{/speckit-analyze}) is held at ``off'' in every condition, so its contribution is not measured. The expected directions were registered in advance; the results are read against them (Section~\ref{sec:results}).

\begin{longtable}{@{}p{0.08\textwidth}p{0.55\textwidth}p{0.30\textwidth}@{}}
\caption{Pre-registered expectations.}\label{tab:hypotheses}\\
\toprule
\textbf{ID} & \textbf{Expectation} & \textbf{Basis} \\
\midrule
\endfirsthead
\toprule
\textbf{ID} & \textbf{Expectation} & \textbf{Basis} \\
\midrule
\endhead
H1a & No consistent difference in stated behaviour (tier A) between conditions & Every condition meets the same stopping rule; naive code already passes 96--100\% of tier A \\
H1b & No directional prediction for security (tier C) & The practice runs showed no difference, but their task text mentioned security \\
H1c & \texttt{sdd\_secure} scores higher on security than \texttt{sdd} & Three 2026 studies~\cite{marri,grynets,dhuri} \\
H2 & SDD runs score higher on traceability & Practice SDD build cited a requirement in every test \\
H3a & SDD costs at least 1.25 times the active time and human turns of unstructured runs & Practice SDD build took about 7 times the agent time \\
H3b & In every SDD run, most active time is spent before implementation & 74\% (R001), 82\% (practice) \\
H3c & \texttt{sdd\_secure} costs about the same as \texttt{sdd} & Only the constitution prompt differs \\
H4a & \texttt{sdd\_clarify} resolves more open points as intended (tier B) than \texttt{sdd} & The practice SDD build's extra correct point came from a question \\
H4b & Without clarification, open points are mostly resolved by assumption & Two of three pilot and practice runs asked nothing \\
H4c & Upstream artifacts are rarely revised after planning & No pilot or practice run revised one \\
H4d & In change requests, SDD runs add a new feature specification and leave the original unedited & Spec Kit creates one feature folder per change \\
H4e & No directional prediction for regression or the change's security & No pilot evidence \\
\bottomrule
\end{longtable}

\subsection{Knowledge-Base Extension}

\textbf{RQ5:} Does the spec-first paradigm generalize from producing software to producing a distilled, queryable knowledge base using OpenOwls SD-KDP, and how does a spec-first approach compare structurally and qualitatively to a more automated, specification-light approach such as OpenKB?

\textbf{RQ5a:} What overhead does authoring OpenOwls SD-KDP's seven specification files impose relative to OpenKB, and what does that overhead buy in terms of provenance, traceability, and output consistency?

\textbf{RQ5b:} Does declaring an explicit Oracle produce a measurably different, more defensible knowledge base than an approach that pursues broader, cross-referenced, less perspective-bound synthesis?

\textbf{RQ5c:} Do the core SDD principles observed in Parts II--III continue to hold when the produced artifact is a knowledge base rather than executable code?

% ----------------------------------------------------------------------
% 4. LITERATURE REVIEW
% ----------------------------------------------------------------------
\section{Literature Review}\label{sec:lit}

\subsection{Security and Correctness of AI-Generated Code}

Pearce et al.\ prompted GitHub Copilot with 89 scenarios built around high-risk CWE weaknesses and found about 40\% of the 1,689 resulting programs vulnerable~\cite{pearce}. Perry et al.\ found in a user study that participants with an AI assistant wrote significantly less secure code than those without one, and were more likely to believe their code was secure~\cite{perry}. These results motivate SDD's premise: if an agent is not told about a requirement, including an implicit security requirement, nothing makes it meet one. They also motivate this study's choice to leave security out of every task description, so that security is measured as the implicit expectation it usually is in practice.

\subsection{Spec-Driven and Constitutional Development Methodologies}

GitHub Spec Kit installs a set of commands into a coding agent~\cite{speckit,speckitblog}. Each command is a prompt template that tells the agent what artifact to produce and what to check: \texttt{/speckit-constitution} writes project principles that later stages must check against; \texttt{/speckit-specify} writes user stories, functional requirements, acceptance scenarios and assumptions, with up to three \texttt{[NEEDS CLARIFICATION]} markers; the optional \texttt{/speckit-clarify} asks up to five targeted questions and writes the answers back into the specification; \texttt{/speckit-plan} writes a technical plan with research notes, a data model, interface contracts and a quickstart; \texttt{/speckit-tasks} writes an ordered, dependency-annotated task list; and \texttt{/speckit-implement} writes code and tests by working through that list.

Several papers formalise or extend this idea. Constitutional SDD embeds CWE-derived security constraints in the constitution and reports a 73\% reduction in security defects against unconstrained generation, in one banking-microservices case study~\cite{marri}. The Specification Governance Reference Model places SDD in an enterprise framework mapped to ISO/IEC 25010~\cite{alenezi}. EPIC scores the specifications of 114 SDD repositories against ISO/IEC/IEEE 29148 and derives 40 practices from the highest-scoring ones, which 15 practitioners endorsed. Repositories in the top third of specification quality spent a smaller share of their commits on bug fixes than those in the bottom third (11.8\% against 20.4\%), though the associations are observational and include no non-SDD repositories~\cite{epic}.

\subsection{Empirical Study Design for LLM-Assisted, Specification-Governed Coding}

The study closest in method is a pre-registered comparison of traceability in three SDD frameworks, including Spec Kit~\cite{panda}. With two models, on 20 and 50 tasks and with three cold-start sessions per task in each condition, mandatory inline requirement citations enabled automated hallucination detection but reduced output determinism. That study compares SDD frameworks with each other, not against prompting without a specification. Rosa et al.\ registered a human-in-the-loop study of specification-first and test-first stages of code generation, using a VS Code extension and LiveCodeBench problems~\cite{rosa}. Its design (matched tasks, instrumented logging, and a mix of effectiveness and efficiency measures) is the methodological template for this study, adapted from stages within one tool to whole workflows.

Two 2026 studies vary the specification an LLM receives. Feng et al.\ ran each configuration 10 times and found that results varied widely with the system and model: a signature model of the existing API raised the average test pass rate by about 7.8\%, while Gherkin scenarios lowered it by 6.8\% on average against a natural-language specification~\cite{feng}. A security benchmark for SDD found fewer failures on a hidden 221-test API suite when specifications were enriched with security requirements~\cite{grynets}. Neither compares an SDD workflow against plain prompting of the same agent. Closest in its comparison is a pre-registered study of five models that sent a fixed 267-word specification frame ahead of single-shot prompts for 50 backend tasks~\cite{dhuri}. Against the bare task text, the frame cut checker findings from 148 to 23 across 250 task pairs. That study states its security constraints explicitly, uses no agent or workflow, and does not test functional correctness; the present study leaves security implicit, uses a full agent workflow, and scores correctness alongside security.

Baltes et al.\ set out guidelines for empirical software engineering studies that use LLMs~\cite{baltes}: report the exact model version, configuration and study dates; publish prompts and session traces; repeat runs to account for non-determinism; validate LLM output against human judgement; and report limitations and their mitigation. This study follows them. It falls short most clearly on repetition, with one run per cell apart from a replicated project (Section~\ref{sec:threats}).

\subsection{Extending Spec-Driven Thinking to Knowledge Artifacts}

OpenOwls SD-KDP~\cite{openowls} applies the spec-first idea to knowledge distillation. A human declares an Oracle (a committed perspective with trusted and rejected sources and the key questions the knowledge base must answer) and writes seven Markdown specification files that an agent reads before every run of a collect, distill and index pipeline. OpenKB takes the specification-light route: documents are added incrementally and compiled automatically into a cross-referenced wiki, with reasoning-based retrieval over long documents instead of a vector index. Table~\ref{tab:partiv-comparison} sets the two side by side.

OpenKB~\cite{openkb} (VectifyAI, Apache-2.0) takes the opposite stance. It compiles documents added at any time into a wiki of plain Markdown pages (per-document summaries, concept and entity pages, an index and a log), connected by wiki links. Each new document is summarized and the existing concept pages are rewritten with cross-document synthesis; contradictions are flagged rather than resolved by a declared perspective. It runs as a command-line tool (\texttt{init}, \texttt{add}, \texttt{query}, \texttt{chat}, \texttt{watch}, \texttt{lint}), calls models through LiteLLM with a provider and model string, and uses PageIndex's reasoning-based retrieval rather than a vector database.

% ----------------------------------------------------------------------
% 5. METHODOLOGY
% ----------------------------------------------------------------------
\section{Methodology}

\subsection{Design Overview}

The study uses a within-subject, task-matched design. Five Python programming tasks of graded size are each built under four conditions with the same agent harness and model, and every build is followed, in the same repository, by a change request (Table~\ref{tab:conditions}). That gives 20 builds and 20 change requests. A replication repeats the smallest task under all four conditions, with its change requests (8 runs), so that run-to-run variation can be set beside the differences between conditions. Two pilot-task runs check the mechanics and are excluded from the analysis.

\begin{table}[h]
\centering
\small
\caption{Conditions.}\label{tab:conditions}
\begin{tabular}{@{}lp{0.68\textwidth}@{}}
\toprule
\textbf{Condition} & \textbf{What the agent gets} \\
\midrule
\texttt{unstructured} & The task text as one message, in one session, with no Spec Kit in the repository (vibe coding) \\
\texttt{sdd} & Spec Kit's default sequence: constitution, specify, plan, tasks, implement; each phase a fresh session \\
\texttt{sdd\_clarify} & The same, with \texttt{/speckit-clarify} between specify and plan \\
\texttt{sdd\_secure} & The same as \texttt{sdd}, with a fifth constitution principle, ``Secure by default'', written from the OWASP Top~10~\cite{owasptop10} and ASVS~\cite{asvs} \\
\bottomrule
\end{tabular}
\end{table}

\textbf{Tasks.} The five tasks were written for this study (Table~\ref{tab:tasks}). Each pins its interface (command, arguments, output format, exit codes, HTTP routes), has a realistic security surface that the text never mentions, plants three or four open points with product-owner answers written in advance, and includes worked examples that serve as the stopping check. The complexity index is the source-line count of the sealed reference implementation.

\begin{table}[h]
\centering
\small
\caption{Study tasks.}\label{tab:tasks}
\setlength{\tabcolsep}{4pt}
\begin{tabular}{@{}lp{0.25\textwidth}cccp{0.2\textwidth}@{}}
\toprule
\textbf{Task} & \textbf{What the agent builds} & \textbf{SLOC (rank)} & \textbf{Stated} & \textbf{Open} & \textbf{Probes (CWE)} \\
\midrule
\texttt{T-REDACT-01} & Log redactor (emails, IPv4, Luhn-valid cards) & 95 (1) & 11 & 4 & 1333/400, 532 \\
\texttt{T-TARX-01} & tar list/extract CLI & 107 (2) & 10 & 3 & 22, 22/36, 59, 732 \\
\texttt{T-BOOKMARKS-01} & SQLite bookmark manager & 124 (3) & 11 & 3 & 89, 155, 1236 \\
\texttt{T-ACCOUNTS-01} & Password account store with lockout & 144 (4) & 15 & 3 & 256/312, 759/916, 204, 732 \\
\texttt{T-PASTE-01} & HTTP paste service & 180 (5) & 13 & 3 & 22, 330, 200, 400/770, 79 \\
\bottomrule
\end{tabular}
\end{table}

\textbf{Change requests.} Each task has one change request written to the same rules, which tells the agent that the project exists and that everything else must keep working: phone numbers and an output folder (\texttt{T-REDACT-01-CR}); a \texttt{create} command (\texttt{T-TARX-01-CR}); import and an HTML export (\texttt{T-BOOKMARKS-01-CR}); one-time password-reset tokens (\texttt{T-ACCOUNTS-01-CR}); and burn-after-reading and password-protected pastes (\texttt{T-PASTE-01-CR}). Each opens a new, unstated security risk, probed for CWE-59, 1333 and 532; 59/200, 22 and 400; 79 and 89; 330/338, 312, 916 and 639; and 362, 256 and 200 respectively. The agent has no memory of the build and knows the project only from its code and documents.

\textbf{Counterbalancing.} Each task's four conditions follow one of the 24 possible orders. Five orders were drawn (seed 20261023) so that every condition is in every serial position at least once, and runs are grouped into four rounds, each holding every task's next condition. A task's builds are therefore at least five runs apart, and each change request follows its build directly.

\textbf{Versions.} Claude Code 2.1.317, model \texttt{claude-opus-5} (the same model string as the pilot), Spec Kit 1.0.6, Python 3.13.17; scoring with pytest 9.1.1 and Bandit 1.9.4. These are the versions recorded in section 11 of the pre-registration at the freeze. The operator's workspace updated Claude Code between restarts, so runs R004 to R011C used 2.1.318 to 2.1.323 and the rerun R019C 2.1.325; every later run uses a pinned copy of 2.1.317 (deviations, Section~\ref{sec:execution}). Each run's version is recorded in its log.

\textbf{Java extension.} Two Java 21/Quarkus tasks (\texttt{T-QNOTES-01}, \texttt{T-QIMPORT-01}) are built under three conditions as six runs, registered in a separate addendum and never pooled with the Python results. The extension was dropped before any Java run was started (see the deviations in the introduction), so no Java results are reported.

\subsection{Procedure}\label{sec:procedure}

Every run is driven by \texttt{run\_build.py}, which sends each fixed prompt to Claude Code in headless mode (\texttt{claude -p}), with the permission mode \texttt{acceptEdits} and a fixed list of allowed tools. The operator types nothing. After each agent turn the operator only classifies it: a question covered by an answer-sheet entry (whose reply is sent verbatim), an uncovered safety question or other question (each with a fixed fallback reply), a request for permission, a list of assumptions that asks nothing, or done. A turn counts as a question when it ends by asking the operator for information or a decision.

\textbf{Stopping rule.} A run is done when \texttt{check\_examples.py} reports that every worked example behaves as shown. Failing examples produce a follow-up in fixed wording, up to 5 follow-ups or 90 minutes after implementation starts.

\textbf{Isolation.} Each run starts from one base repository (instrument and hooks only; base commit \texttt{c5bf438}), in a fresh clone. Web tools are denied. Every agent session gets a minimal environment and its own empty Claude Code configuration, so no user skills, plugins, hooks or host tools reach the agent and nothing carries over between runs. The SDD conditions add Spec Kit in one setup commit, because its commands are model-invocable skills that would otherwise contaminate the \texttt{unstructured} condition. No human reviews or edits the generated specifications, so the study tests SDD as an agent-driven workflow with a human product owner.

\textbf{Operator.} The Python study runs are operated by Claude, the AI assistant that drafted the study materials, in Anthropic's cloud workspace. Because it also wrote the hidden tests, its only inputs are the fixed choices above, each logged with the message it answered, and the author reviews every classification afterwards.

\subsection{Instrumentation}

Spec Kit was configured with the Claude Code integration. All prompts, generated specifications, plans, task lists, code diffs, and final outputs were logged. For the unstructured condition, the same agent was used with only the bare task description as input, with follow-up prompts logged in the same format.

The logging instrument \texttt{sddlog} (version 1.3, 80 tests) records every run through three overlapping paths, so that no single misconfiguration can silently produce an empty or misleading entry: Claude Code hooks (session start, prompt submit, tool use and stop) capture prompts, tool calls and edits in real time; a git commit and diff at every phase boundary gives exact line counts; and the session transcripts give token usage per model message, counting each message once and including sub-agents. Spec Kit artifacts are hashed and snapshotted at every phase boundary, which makes specification revisions measurable, and a verification gate checks six integrity conditions before a run enters the dataset.

\begin{table}[h]
\centering
\small
\caption{Study tools (repository \texttt{tools/}).}\label{tab:tools}
\begin{tabular}{@{}lp{0.58\textwidth}@{}}
\toprule
\textbf{Tool} & \textbf{Role} \\
\midrule
\texttt{sddlog/sddlog.py} & Logging instrument: event log, metrics, snapshots, verification gate \\
\texttt{study/run\_build.py} & Drives each run in headless mode; the operator only classifies turns (20 tests) \\
\texttt{study/check\_examples.py} & Stopping-rule check against the task's worked examples \\
\texttt{study/score\_run.py} & Scores a run against the sealed suites, with Bandit; computes the suites' tree hash \\
\texttt{study/make\_schedule.py} & Draws the counterbalanced schedule from seed 20261023 \\
\texttt{study/make\_coding\_sheets.py} & Creates the traceability, security and principles coding sheets for each scored run \\
\texttt{study/analyze.py} & The pre-registered analysis: tables, decision rule, exact tests (15 tests) \\
\bottomrule
\end{tabular}
\end{table}

\subsection{Metrics}

\begin{itemize}[leftmargin=*]
    \item \textbf{Functional correctness:} pass rate against a held-out test suite for each task, in two tiers: tier A tests what the task text states (107 cases for the builds, 65 for the change requests), and tier B tests the open points against the product owner's answers (16 and 16 cases). Every test runs the agent's code as a black box.
    \item \textbf{Security-relevant defect rate:} tier C probes, each mapped to a CWE (34 cases for the builds, 26 for the change requests); Bandit 1.9.4 over product code; and a manual review against a fixed checklist. Each candidate finding is coded with CWE, location and severity (High, Medium or Low), and only findings confirmed by hand are counted; probes failing for one root cause count once.
    \item \textbf{Requirement traceability:} one row per stated and intent requirement, scored 2 when the requirement is met with an identifiable code location and an agent-written test that exercises it, 1 when met without such a test, and 0 otherwise. Coverage is the mean score divided by 2; the explicit-link rate is the share of requirements whose code or tests cite a requirement or specification ID.
    \item \textbf{Time and effort:} active agent time (the sum over phases of the time from each phase's start to its last hook-observed agent activity, so that a late phase marker adds nothing), human turns, and tokens (all input tokens including cache reads and writes, plus output tokens). Wall-clock time is recorded but is not the measure, because it counts operator delays.
    \item \textbf{Regression:} the original task's tiers A and C, run again on the repository after its change request.
    \item \textbf{Behaviour:} questions asked and answer-sheet entries elicited, assumptions listed, specification revisions after planning, and how many of three checkable constitution principles the code meets.
    \item \textbf{Output determinism:} measured as run-to-run variation. The replication runs (R021--R023, R039) repeat \texttt{T-REDACT-01} under every condition, and every measure is compared between the two runs of the same cell. No lexical similarity metric is used, because the black-box tests already compare behaviour.
\end{itemize}

\subsection{Analysis Plan}

Given the small expected sample size, the analysis was primarily descriptive and qualitative, supplemented with paired comparisons where sample size permitted. Results are framed as exploratory evidence rather than a definitive test of SDD's effectiveness.

The unit is the run. Builds and change requests are analysed separately and never pooled, and every result is reported task by task for all six pairs of conditions. A difference is called \emph{consistent} only if it has the same direction in at least 4 of the 5 tasks (ties count against) and its median paired difference reaches a minimum fixed in advance: 10 percentage points for pass rates and traceability coverage, a ratio of 1.25 (or 0.8) for time, turns and tokens, and 1 for confirmed findings. Otherwise the result is ``no consistent difference''.

The tests are reported for completeness, not relied on: an exact Friedman test across the four conditions (with 5 tasks the smallest attainable $p$ is about $3\times10^{-6}$), exact two-sided Wilcoxon signed-rank tests for the six pairs with Holm's correction (the smallest attainable $p$ is 0.0625, so no pairwise test can reach $\alpha = 0.05$), the matched-pairs rank-biserial correlation, and Spearman's $\rho$ between complexity rank and each measure within each condition (smallest $p$ 0.017). All of it is computed by \texttt{analyze.py}, written and tested before any study run against these exact values, and its output is reported unedited.

\textbf{Coding.} Traceability, security and principle sheets are coded per run; all runs of one task are coded in one sitting, in an order drawn with the same seed. A random 30\% of traceability rows is re-coded by the same coder at least five days later without the first codes, and weighted Cohen's $\kappa$ is reported. There is no second coder.

\subsection{Pilot, Practice Comparison and Mechanics Checks}\label{sec:prelim}

Five runs were made before the study runs. All are excluded from the study's data and show how the method behaves, not effects.

\textbf{Pilot R001} (Weeks 3--4) took the expense splitter \texttt{T-SPLIT-01} through Spec Kit's full sequence: 29 minutes of active agent time, five human prompts, 58 passing tests and 168 lines of product code. The specification phases took 74\% of the active time and produced 7,580 words from 278 words of human input, and no upstream document was revised after it was written.

\textbf{Practice comparison} (Week 6) built a login page once with plain prompting and once with Spec Kit, scored against 41 hidden checks frozen beforehand. The builds came from sub-agents outside the study's harness, so the numbers show the method working, not a result.

\begin{table}[h]
\centering
\small
\caption{Practice comparison, \texttt{T-LOGIN-01} (excluded from the study).}\label{tab:practice}
\begin{tabular}{@{}lcc@{}}
\toprule
\textbf{Measure} & \textbf{Unstructured (D001)} & \textbf{Spec Kit (D002)} \\
\midrule
Tier A, stated behaviour & 22/22 & 22/22 \\
Tier B, open points & 1/4 & 2/4 \\
Tier C, security probes & 15/15 & 15/15 \\
Confirmed security findings & 0 & 0 \\
Tests citing a requirement & 0 of 72 & 90 of 90 \\
Agent working time & 23.5 min & about 160 min \\
Agent tokens & about 118,000 & about 945,000 \\
Human turns & 1 & 7 \\
\bottomrule
\end{tabular}
\end{table}

The practice task's text mentioned security, and both builds were secure; the study's task texts do not. Spec Kit asked two questions, got one more open point right and was fully traceable, at about 7 times the time and 8 times the tokens.

\textbf{Mechanics checks R002 and R003} (3 November 2026) ran the pilot task with the full study procedure, under \texttt{unstructured} and \texttt{sdd\_clarify}.

\begin{table}[h]
\centering
\small
\caption{Mechanics checks, \texttt{T-SPLIT-01} (excluded from the study).}\label{tab:mechanics}
\begin{tabular}{@{}lcc@{}}
\toprule
\textbf{Measure} & \textbf{R002 unstructured} & \textbf{R003 sdd\_clarify} \\
\midrule
Result & All examples pass; integrity 6/6 & All examples pass; integrity 6/6 \\
Phases & 1 & 6 \\
Active agent time & 7.9 min & 32.8 min \\
Human turns & 1 & 7 \\
Tokens (input incl.\ cache, plus output) & 1.86 million & 8.54 million \\
Cost estimate reported by Claude Code & \$2.49 & \$12.19 \\
Questions asked & 0 & 1 \\
\bottomrule
\end{tabular}
\end{table}

They confirmed that every Spec Kit phase works in headless mode, that the logging hooks survive Spec Kit's setup, and that \texttt{sddlog}'s output-token counts agree with Claude Code's own figures within 6\%. They also found one problem: the fixed fallback reply ``No preference. Use your judgement.'' was read by the agent as handing over all remaining clarification questions, so it answered four of its five itself. Before the freeze (4 November 2026) both fallback replies were therefore scoped to one question (``No preference on this question. Use your judgement.''), and two operator rules were added: Spec Kit's optional commit-hook messages are not questions, and a turn that ends with an offer but asks for nothing is classified as listed.

\subsection{Threats to Validity}

\begin{itemize}[leftmargin=*]
    \item \textbf{Construct validity:} chosen metrics may not capture all dimensions of code quality.
    \item \textbf{Internal validity:} familiarity with each task could change how the operator handles later runs; mitigated by counterbalancing, fixed replies and an audit of every operator decision.
    \item \textbf{External validity:} findings from five small tasks, one agent and one model may not generalize to team settings or larger codebases.
    \item \textbf{Researcher bias:} the test suites, rubrics, prompts, answer sheets, decision rules and analysis code were all fixed and sealed before any study run.
\end{itemize}

The full analysis is in Section~\ref{sec:threats}.

\subsection{Part IV Design: Extending SDD to Knowledge-Base Production}\label{sec:method-partiv}

Part IV followed the OpenOwls SD-KDP six-step workflow: declaring an Oracle for a bounded knowledge domain; authoring the seven \texttt{ai\_specs/} files; implementing \texttt{collect.py} and \texttt{distill.py} against a real source corpus; running the pipeline manually against a single source and iterating on the specification rather than the generated output; scheduling the pipeline to run unattended and verifying incremental, hash-based re-processing; and querying the resulting wiki against the Oracle's key questions as the acceptance test.

The resulting SD-KDP-built knowledge base was compared against OpenKB along a fixed set of structural dimensions. The comparison is qualitative and structural rather than a head-to-head benchmark of output quality.

The plan is as follows. The Oracle's domain is the research literature on spec-driven development, with at least three sources it rejects and a list of key questions. The seven specification files cover the overview, domain knowledge, the Oracle, collection, distillation, output format and the batch process. The corpus is 15--20 sources (preprints, the Spec Kit documentation and blog posts, practitioner reports), each with its URL and licence. OpenKB is then built on the same corpus with the same LLM, both wikis are asked the Oracle's key questions, and the structural comparison in Table~\ref{tab:partiv-comparison} is filled in.

\textbf{Oracle.} The Oracle is \emph{the evidence-first software engineer}: an engineer deciding whether to adopt SDD, who treats it as a hypothesis about engineering practice. A claim about effect counts only as far as a study with a stated method supports it; tool documentation is authoritative about what a tool does, not whether it works; named practitioners' hands-on reports are kept as observations. Every statement in the knowledge base carries a source tag and one of six evidence classes (measured, reported case, observed, documented, claimed, argued). The Oracle rejects three sources by name: a sponsored article written by the vice-president of AWS's own SDD product; an unattributed copy of that article; and a podcast episode whose page states it was generated with AI hosts. It also sets standing rules for rejecting sources added later. Its eight key questions (what SDD is and how the tools differ; measured evidence on correctness; on security; cost; existing codebases; traceability; practitioner criticisms; what remains unknown) are the acceptance test. The author approved the Oracle on 14 November 2026.

\textbf{Specifications and corpus.} The seven specification files are \path{overview.md}, \path{domain-knowledge.md}, \path{oracle.md}, \path{collection-techniques.md}, \path{distillation-techniques.md}, \path{output-format.md} and \path{batch-process.md}, in \path{part-iv/ai_specs/}. The corpus has 17 trusted sources in four tiers: seven papers (empirical studies, a registered study design, a single case study and a position paper), four sets of tool documentation and announcements, and six practitioner analyses. Each URL, date and licence was checked on the source page. Full texts stay local; the wiki holds original summaries with at most two short quotes per article.

\textbf{Pipeline.} \path{collect.py} fetches each trusted source and records a SHA-256 hash of its text; \path{distill.py} writes one article per new or changed source from that source alone, then runs a voice check: deterministic rules (source tags, evidence classes, a hype-word list, a hedge-density limit, quote limits, template sections) followed by one model review against the Oracle. An article that fails twice is not written, and the specification, not the article, is changed. \path{synthesize.py} builds one page per key question, an FAQ and an index; \path{index.py} builds a TF-IDF vector index used by \path{query.py}; \path{batch.sh} runs the steps nightly and commits the wiki. The model is called only through \path{llm.py}, using the author's Claude subscription.

The pipeline was first run on a single source (S08, the Spec Kit methodology document). Collection extracted the text and recorded its SHA-256 hash; distillation produced one article that passed the voice check on the first attempt; the incremental check confirmed that a second run with the same hash produced no re-distillation. The full-corpus run is pending. OpenKB will be built on the same corpus for the structural comparison; it requires an API key or OAuth provider rather than a Claude subscription.

% ----------------------------------------------------------------------
% 6. RESULTS
% ----------------------------------------------------------------------
\section{Results}\label{sec:results}

Every table in this section is produced by \texttt{analyze.py} from the scored runs. Builds and change requests are reported separately; each verdict follows the decision rule above.

\subsection{Software SDD Study: Functional Correctness and Defects}

\begingroup\small\setlength{\tabcolsep}{4pt}
\begin{longtable}{@{}llccccc@{}}
\caption{Builds: correctness and security by task and condition.}\label{tab:correctness-defects}\\
\toprule
\textbf{Task} & \textbf{Condition} & \textbf{Tier A} & \textbf{Tier B} & \textbf{Tier C} & \textbf{Findings} & \textbf{High+Med} \\
\midrule
\endfirsthead
\toprule
\textbf{Task} & \textbf{Condition} & \textbf{Tier A} & \textbf{Tier B} & \textbf{Tier C} & \textbf{Findings} & \textbf{High+Med} \\
\midrule
\endhead
GRID5
\bottomrule
\end{longtable}
\endgroup

\begingroup\small\setlength{\tabcolsep}{4pt}
\begin{longtable}{@{}llcccc@{}}
\caption{Change requests: correctness, security and regression.}\label{tab:change-requests}\\
\toprule
\textbf{Task} & \textbf{Condition} & \textbf{CR tier A} & \textbf{CR tier C} & \textbf{Regression} & \textbf{Findings} \\
\midrule
\endfirsthead
\toprule
\textbf{Task} & \textbf{Condition} & \textbf{CR tier A} & \textbf{CR tier C} & \textbf{Regression} & \textbf{Findings} \\
\midrule
\endhead
GRID4
\bottomrule
\end{longtable}
\endgroup

\textbf{Verdicts.} \emph{Tier~A (P1):} No pairwise comparison reached the consistency threshold; Friedman $p = 1.00$. \emph{Tier~C (P2):} No pair was consistent (Friedman $p = 0.25$), though \texttt{sdd\_secure} improved over all other conditions on 2 of 5 tasks (T-REDACT-01: 70\% $\to$ 100\%; T-PASTE-01: 83\% $\to$ 100\%). \emph{CR tier~A (P9):} All conditions achieved 100\% on every task; Friedman $p = 1.00$. \emph{Regression (P9):} No consistent pairwise difference; Friedman $p = 1.00$. \emph{CR tier~C (P10):} No consistent pairwise difference; Friedman $p = 1.00$; \texttt{sdd\_secure} scored 89\% versus 67\% on T-REDACT-01-CR. Confirmed findings by CWE: across the 25 builds, 26 of 55 candidate findings were confirmed---CWE-1333/400 (ReDoS timeout, 18), CWE-1236 (CSV formula injection, 4), CWE-79 (missing \texttt{nosniff}, 3), CWE-703 (\texttt{assert} in production, 1). All 29 Bandit B105 (CWE-259) findings were false positives (error messages, CLI argument names and field names matching the ``hardcoded password'' pattern). Across the 25 change-request runs, 20 of 49 candidates were confirmed---CWE-59 (link following, 15), CWE-1333/400 (3), CWE-703 (1), plus 1 from R006C.

\subsection{Requirement Traceability}

\begingroup\small\setlength{\tabcolsep}{4pt}
\begin{longtable}{@{}llccc@{}}
\caption{Requirement traceability. Coverage = mean score / 2; explicit-link rate = share of requirements whose code or tests cite a specification ID.}\label{tab:traceability}\\
\toprule
\textbf{Task} & \textbf{Condition} & \textbf{Requirements coded} & \textbf{Coverage} & \textbf{Explicit-link rate} \\
\midrule
\endfirsthead
\toprule
\textbf{Task} & \textbf{Condition} & \textbf{Requirements coded} & \textbf{Coverage} & \textbf{Explicit-link rate} \\
\midrule
\endhead
GRID3
\bottomrule
\end{longtable}
\endgroup

\textbf{Verdicts (P3).} Coverage was high in every condition (79--100\% per task). No pairwise comparison reached the consistency threshold (Friedman $p = 0.57$). The main contrast, \texttt{sdd} versus \texttt{unstructured}, showed no consistent difference (median $+0$~pp, same direction 2 of 5 tasks). The explicit-link rate was 0\% in every unstructured run and 94--100\% in every SDD run, confirming that SDD produces machine-traceable requirement citations. Cohen's $\kappa$ from re-coding will be added after the 30\% re-code pass.

\subsection{Time and Effort}

\begingroup\small\setlength{\tabcolsep}{4pt}
\begin{longtable}{@{}llcccc@{}}
\caption{Time and effort for the builds, from each run's log. All 20 study builds. $^{\dagger}$Session interrupted and resumed: time recomputed from event timestamps with idle gaps over 10 minutes removed; the same recomputation agrees with the logged value within 1\% on the uninterrupted runs.}\label{tab:time-effort}\\
\toprule
\textbf{Task} & \textbf{Condition} & \textbf{Active time} & \textbf{Turns} & \textbf{Tokens} & \textbf{Before impl.} \\
\midrule
\endfirsthead
\toprule
\textbf{Task} & \textbf{Condition} & \textbf{Active time} & \textbf{Turns} & \textbf{Tokens} & \textbf{Before impl.} \\
\midrule
\endhead
GRIDTIME
\bottomrule
\end{longtable}
\endgroup

\textbf{Verdicts (P4).} Active time differed significantly across conditions (Friedman $p = 0.0023$). Every SDD variant was consistently slower than unstructured prompting: unstructured versus \texttt{sdd} showed a median ratio of 0.13$\times$ (5 of 5 tasks same direction), and unstructured versus \texttt{sdd\_secure} 0.01$\times$ (5 of 5). Human turns (Friedman $p = 3.0 \times 10^{-5}$) and tokens (Friedman $p = 0.0055$) showed the same pattern. Pairwise Wilcoxon tests did not reach $p < 0.05$ after Holm correction, as the maximum exact $p$ with five tasks is 0.0625. \emph{Complexity scaling:} Spearman correlations between task complexity rank and each measure were non-significant in every condition except \texttt{sdd\_secure} active time ($\rho = -1.00$, $p = 0.017$), where the most complex task took the most time. \emph{Change-request costs:} CR active time (Friedman $p = 0.044$), CR tokens (Friedman $p = 0.0001$) and CR human turns (Friedman $p = 3.0 \times 10^{-5}$) were all significantly different; unstructured CRs were consistently cheaper than any SDD variant.

\subsection{Workflow Component Contribution}

\textbf{P5 (Tier~B, \texttt{sdd\_clarify} vs.\ \texttt{sdd}).} Tier~B pass rates were low and variable across all conditions (0--100\% per task). No pairwise comparison reached the consistency threshold (Friedman $p = 0.91$). \texttt{sdd\_clarify} scored higher than \texttt{sdd} on 2 of 5 tasks (T-BOOKMARKS-01: 33\% vs.\ 0\%; T-PASTE-01: 67\% vs.\ 33\%), tied on 2 and scored lower on 1 (T-TARX-01: 67\% vs.\ 100\%).

\textbf{P6 (Post-plan revisions).} Specification revisions after the plan was written were rare: across 15 SDD builds (excluding unstructured, which has no specification), there were 10 total revisions, concentrated in T-REDACT-01 (5 of 10). The median was 0 revisions per run.

\textbf{P7 (Principles met).} The three constitution principles---standard library only, fail loudly, every requirement testable---were coded for all 25 builds (75 rows). All 25 runs met ``standard library only'' and ``every requirement testable'' ($\geq$80\% of stated requirements scored~2). ``Fail loudly'' was met by 14 of 25 runs; the 11 violations were \texttt{except} blocks with \texttt{pass} in product code (e.g.\ cleanup, shutdown, retry patterns). By condition: \texttt{sdd\_clarify} met all three principles in every run (7/7); \texttt{sdd\_secure} and \texttt{sdd} each had violations in 3--4 of 6 runs; \texttt{unstructured} had violations in 4 of 6. No pairwise comparison reached the consistency threshold (Friedman $p > 0.05$).

\textbf{P8 (Security in the constitution).} The \texttt{sdd\_secure} condition wrote CWE-derived security constraints into the constitution. On the two tasks where the hidden probes test for those specific weaknesses (T-REDACT-01 and T-PASTE-01), \texttt{sdd\_secure} achieved 100\% tier~C versus 70\% and 83\% for all other conditions. On the other three tasks, security scores were identical across conditions. CR tier~C showed a similar but smaller pattern on T-REDACT-01-CR (89\% vs.\ 67--78\%).

\textbf{P11 (CR edits the specification).} In 14 of 15 SDD change-request runs, the agent did not edit the original build's specification. The single exception was R006C (\texttt{sdd\_secure}, T-REDACT-01-CR).

\subsection{Output Determinism}

\begin{table}[h]
\centering
\small
\caption{Run-to-run variation: \texttt{T-REDACT-01} built twice per condition.}
\label{tab:determinism}
\begin{tabular}{@{}lcccc@{}}
\toprule
\textbf{Condition} & \textbf{Runs} & \textbf{$\Delta$ Tier A} & \textbf{$\Delta$ Tier C} & \textbf{$\Delta$ Active time} \\
\midrule
\texttt{unstructured} & R036, R023 & +0\,pp & +0\,pp & $-$0.1\,min \\
\texttt{sdd} & R016, R022 & +0\,pp & +30\,pp & $-$811.0\,min \\
\texttt{sdd\_clarify} & R011, R021 & +0\,pp & +0\,pp & $-$18.2\,min \\
\texttt{sdd\_secure} & R006, R039 & +0\,pp & +0\,pp & $-$5777.3\,min \\
\bottomrule
\end{tabular}
\end{table}

The replicated pairs show that tier~A pass rates were perfectly stable across runs in all four conditions ($\Delta = 0$\,pp). Tier~C was likewise stable in three conditions but varied by 30\,pp in \texttt{sdd} (one run passed 70\%, the other 100\%). Active-time variation was negligible for \texttt{unstructured} ($-$0.1\,min) but large for the SDD conditions, reaching $-$5{,}777\,min for \texttt{sdd\_secure}. This suggests that while functional correctness is reproducible, the agent's path through the SDD workflow is not: the same specification can lead to very different amounts of work, and a single security probe can pass or fail depending on the run. The between-condition tier~C differences (unstructured 70\% vs.\ \texttt{sdd\_secure} 100\%) are of the same magnitude as the within-condition \texttt{sdd} variation, so the security effect of \texttt{sdd\_secure} on T-REDACT-01 should be interpreted with caution.

% ----------------------------------------------------------------------
% 7. VALIDATION
% ----------------------------------------------------------------------
\section{Validation}

Each validation item must be completed and evidenced before the report is submitted. The instrument-level checks made before the study runs are recorded below and in Appendix~\ref{app:log}. All results-level checks for the software study (Parts II--III) are complete, including confirmed-findings adjudication; Part IV structural validation remains open.

\subsection{Validation Checklist}

\begin{longtable}{@{}p{0.20\textwidth}p{0.26\textwidth}p{0.26\textwidth}p{0.20\textwidth}@{}}
\caption{Validation checklist. Result fields stay empty until each check is evidenced.}\\
\toprule
\textbf{Validation item} & \textbf{Criterion} & \textbf{Evidence required} & \textbf{Result} \\
\midrule
\endfirsthead
\toprule
\textbf{Validation item} & \textbf{Criterion} & \textbf{Evidence required} & \textbf{Result} \\
\midrule
\endhead
Functional correctness & Held-out tests pass per pre-registered threshold & Test logs, pass/fail summary & Suites validated before freezing; study runs: 48 runs scored (73 score files) \\
Security defects & Static analysis and manual review completed & SAST report, CWE mapping, review notes & Probes and Bandit validated on reference and naive code; study runs: Bandit run on all 48 builds \\
Requirement traceability & Every acceptance criterion coded to code change or marked untraced & Traceability matrix & Requirement register built (245 rows); coding complete (379 rows across 25 runs) \\
Time and effort & Active time, turns and tokens logged consistently & Timestamped logs & Logging verified in R002 and R003; study runs: 48 runs logged, metrics extracted \\
Output determinism & Replicated cells compared on every measure & Run-to-run variation table & Table~\ref{tab:determinism} filled \\
Researcher bias & Rubrics and test suites pre-registered where feasible & Pre-registration record & Suites sealed 24 and 31 Oct 2026 with hashes; frozen 4 Nov 2026 (merge commit \texttt{5a58b4f}), hashes emailed to the advisor the same day; unsealing: suites unsealed 22 Nov 2026, hashes verified \\
Part IV structural comparison & Fixed dimensions applied to both SD-KDP and OpenKB & Comparison table and notes & Structural dimensions compared from documentation (Table~\ref{tab:partiv-comparison}); full-corpus pipeline execution deferred \\
Reproducibility & Environment, model versions, and scripts documented & Repository and configuration files & Versions, base repository and run bundles in the repository; final check: confirmed---environment table, model and tool versions, run bundles and analysis scripts are in the repository \\
Ethics and data handling & No sensitive data; sources documented & Data statement & Synthetic tasks, no personal data (Section~\ref{sec:repro}); final check: confirmed---all five tasks are synthetic, no personal or proprietary data, no human subjects \\
\bottomrule
\end{longtable}

\subsection{Functional Correctness Validation}

Before sealing, each suite was run against two kinds of implementation: the reference implementation, which must pass everything, and deliberately naive implementations written as plausible first drafts that meet the task text but take common shortcuts. For the builds, the references passed every case; naive code passed 96--100\% of tier A but only 0--70\% of tier C. For the change requests, the references passed all 107 cases on three separate runs. An independent alternative implementation, run under 22 alternative readings of the change-request texts, passed tiers A and C in every one; it failed only tier B readings that differ from the product owner's answer, which is what tier B measures. Every naive variant meets the stopping rule, so the worked examples do not leak the hidden tests.

The sealed suites were unsealed on 22 November 2026 after the last study run (R039C) closed. The tree hashes of the decrypted archives matched those recorded in the pre-registration (Section~11). All 48 runs (25 builds, 23 change requests; R011C excluded, replaced by R019C) were scored using \texttt{score\_run.py} with pytest 9.1.1 and Bandit 1.9.4, producing 73 score JSON files. No test was excluded from scoring.

\subsection{Security Defect Validation}

Security findings come from three sources: failed tier C probes, Bandit 1.9.4 over product code (tests, logs, tools and Spec Kit files excluded), and a manual review against a fixed checklist (for example, SQL built by string formatting even where no probe exploits it, or a password hash that meets no OWASP Password Storage configuration). Every candidate is coded with CWE, location, severity and \emph{confirmed} (yes or no), and only confirmed findings count. On the change-request validation code, Bandit flagged only the string-built SQL and the use of \texttt{random} for tokens. It missed link following, archive dereferencing, missing HTML escaping, plaintext secrets and a burn-after-reading race, which the probes caught. This is why the three sources are combined.

Adjudication of candidate security findings from the study runs is complete. Each candidate finding from failed tier~C probes and Bandit reports was coded with CWE, location, severity and confirmed status. \textbf{Builds:} 55 candidates across 25 runs; 26 confirmed (CWE-1333/400: 18, CWE-1236: 4, CWE-79: 3, CWE-703: 1), 29 not confirmed (all 29 Bandit B105/CWE-259 ``hardcoded password'' findings were false positives---error messages, CLI argument names, field names, header names, replacement tags, algorithm names and CLI separators). \textbf{Change requests:} 49 candidates across 25 CR runs; 20 confirmed (CWE-59: 15, CWE-1333/400: 3, CWE-703: 1, plus 1 from R006C), 29 not confirmed. The confirmed-findings table (Table~\ref{tab:results}) reports only confirmed findings.

\subsection{Traceability Validation}

The requirement register (\texttt{coding/requirements.csv}) holds one row per requirement of every task, each linked to the hidden tests that check it: 97 for the Python builds, 84 for their change requests and 64 for the Java builds. For each scored run, \texttt{make\_coding\_sheets.py} creates a sheet with one row per stated and intent requirement, on which the coder records the code locations, any agent-written test, any specification IDs and whether code or tests cite them. Reliability is checked by re-coding 30\% of rows at least five days later.

Traceability coding is complete: 379~requirement rows across 25~base Python runs have been coded with code locations, agent-written tests, specification IDs, and explicit-link status. Coverage (mean score / 2) ranges from 79\% to 100\% per task across all conditions. The 30\% re-coding sample and Cohen's $\kappa$ will be added after the re-code pass (at least five days after the initial coding).

\subsection{Time and Effort Validation}

Active time is derived from agent-side hook timestamps, so a late phase marker or an operator delay adds nothing; phases with excessive trailing idle are flagged by the verification gate. Token counts come from the session transcripts and are cross-checked against Claude Code's own per-call usage records. In the mechanics checks the two sources agreed within 2.2\% (R002) and 5.6\% (R003).

\textbf{Final status (22 November 2026, all 48 Python runs closed).} Each run's integrity check was re-run on the archived logs: 47 runs pass all six checks with no warning; R011C fails three (a duplicated sequence number and doubled phase markers, from two copies of the run tool) and is excluded (Section~\ref{sec:execution}), replaced by R019C. Each run's final code was restored from its git bundle and its worked examples run again: all 48 meet the stopping rule, and none reached the follow-up or time cap. The run log agrees with every run's own logs on follow-ups, cap and cost. Active time for interrupted runs is recomputed as described above.

\textbf{Public test sweep, 21 November 2026.} Every public test group in the repository was run in GitHub Actions (run 44930674082, revision \texttt{f98c6ba}, Python 3.13.18, pytest 9.1.1): 681 cases, 675 passed, 5 failed, 1 skipped.

\begin{center}\small
\begin{tabular}{@{}lrrrr@{}}
\toprule
Test group & Passed & Failed & Skipped & Total \\
\midrule
Main application & 58 & 0 & 0 & 58 \\
Study logging, run tool and frozen analysis & 143 & 0 & 0 & 143 \\
Part IV knowledge-base pipeline & 22 & 0 & 0 & 22 \\
Practice D001, its own tests & 133 & 0 & 0 & 133 \\
Practice D002, its own tests & 242 & 0 & 1 & 243 \\
Practice held-out tests on D001 & 38 & 3 & 0 & 41 \\
Practice held-out tests on D002 & 39 & 2 & 0 & 41 \\
\midrule
Total & 675 & 5 & 1 & 681 \\
\bottomrule
\end{tabular}
\end{center}

All study tooling passed, and the 46 archived run logs passed all six integrity checks. The five failures are in the public practice login task (T-LOGIN-01), not the study: D001 misses lockout after five failures, case-insensitive usernames and the redirect from the login page when signed in; D002 misses the last two. The one skip needs Python 3.11, which the runner lacks. The sweep does not run the sealed study suites, which stay sealed until R039 and R039C close.

\subsection{Part IV Structural Validation}

The Part~IV structural comparison has not yet been validated. The five comparison dimensions in Table~\ref{tab:partiv-comparison} (governing artifact, stance toward bias, execution model, retrieval mechanism, definition of done) were fixed before either tool was run. Validation will check that each dimension's description matches the tool's actual behaviour on the shared corpus and that the observed-result row is filled from the pipeline outputs.

% ----------------------------------------------------------------------
% 8. PART IV RESULTS: KNOWLEDGE-BASE PRODUCTION
% ----------------------------------------------------------------------
\section{Part IV Results: Knowledge-Base Production}

The SD-KDP pipeline has been validated on a single source (S08). The full-corpus run and head-to-head comparison against OpenKB are pending completion of the pipelines on the shared 17-source corpus.

\subsection{OpenOwls SD-KDP Implementation}

The Oracle, the seven specification files, the 17-source corpus and the pipeline are described in Section~\ref{sec:method-partiv} and are in \path{part-iv/}. The pipeline's 18 offline tests pass (voice check, extraction, incremental collection and distillation, front matter, FAQ, index and vector query). Collection was first run on S08, the Spec Kit methodology document; a second run found it unchanged and passed nothing to distillation.

\subsection{Structural Comparison Against OpenKB}

\begin{table}[h]
\centering
\caption{Structural comparison dimensions for Part IV.}
\label{tab:partiv-comparison}
\begin{tabular}{@{}p{0.18\textwidth}p{0.34\textwidth}p{0.34\textwidth}@{}}
\toprule
\textbf{Dimension} & \textbf{OpenOwls SD-KDP} & \textbf{OpenKB} \\
\midrule
Governing artifact & Seven human-authored Markdown specs in \texttt{ai\_specs/}, tracked in git and read by the agent before any run & Primarily automatic compilation from added documents; lighter, config-driven setup rather than multi-file human specification \\
Stance toward bias & Explicit Oracle declaring a committed perspective and bounded, reviewable set of trusted and rejected sources & Implicit toward broader synthesis; cross-references built and contradictions flagged rather than resolved by declared stance \\
Execution model & Unattended nightly batch pipeline: collect $\rightarrow$ distill $\rightarrow$ index $\rightarrow$ backup & Incremental CLI workflow: init / add / query / chat; documents addable at any time \\
Retrieval mechanism & Vector index built over the distilled wiki & PageIndex vectorless, reasoning-based retrieval over long documents \\
Definition of done & Oracle's declared key questions answered accurately, in Oracle's voice, from distilled base & Compiled wiki's cross-references current and knowledge compounds across additions \\
Observed result & Pipeline not executed in the study window; structural comparison drawn from documentation and published guides & Pipeline not executed in the study window; structural comparison drawn from documentation and repository README \\
\bottomrule
\end{tabular}
\end{table}

The Part~IV comparison is structural and qualitative; the full-corpus run and the head-to-head qualitative assessment addressing RQ5a--c are pending completion of the SD-KDP and OpenKB pipelines on the shared corpus.

% ----------------------------------------------------------------------
% 9. DISCUSSION
% ----------------------------------------------------------------------
\section{Discussion}

The findings are discussed in relation to the registered expectations in Table~\ref{tab:hypotheses}.

\textbf{RQ1 (Correctness and Security).} H1a expected no consistent difference in tier~A between conditions, and this was confirmed: every condition scored 96--100\% on stated behaviour, and the Friedman test was non-significant ($p = 1.00$). The near-ceiling result suggests that Claude Code's \texttt{claude-opus-5} already solves these small standard-library tasks reliably from an unstructured prompt, leaving no room for SDD to improve on. H1b made no directional prediction for tier~C; the data show no consistent pairwise difference (Friedman $p = 0.25$), but H1c---that \texttt{sdd\_secure} would score higher than \texttt{sdd} on security---is partially supported. The improvement appeared on 2 of 5 tasks (T-REDACT-01 and T-PASTE-01), precisely those whose security-relevant behaviour the constitution addresses. On the other three tasks, all conditions scored identically. This suggests that constitutional security constraints help only when they match the security risks present in the task, an observation consistent with the finding of Grynets et al.~\cite{grynets} that specification enrichment reduces failures on a hidden API security suite.

\textbf{RQ2 (Maintenance).} H4e expected no directional prediction for regression or the change's security. CR tier~A was 100\% across all conditions, and CR tier~C showed no consistent difference (Friedman $p = 1.00$). The \texttt{sdd\_secure} advantage was visible on T-REDACT-01-CR (89\% vs.\ 67--78\%) but not strong enough to reach the consistency threshold. Regression scores (original tiers A and C preserved after the change) were likewise indistinguishable across conditions.

\textbf{RQ3 (Cost).} H3a expected SDD to cost at least 1.25 times the active time and human turns of unstructured runs, and this was confirmed by a wide margin. The median ratio of unstructured to \texttt{sdd} active time was 0.13$\times$ (i.e., SDD took roughly 8 times longer), and the ratio to \texttt{sdd\_secure} was 0.01$\times$ (roughly 100 times longer). Human turns and tokens showed the same pattern. All three Friedman tests were highly significant ($p = 0.0023$, $p = 3.0 \times 10^{-5}$, $p = 0.0055$). H3b expected most active time to be spent before implementation in every SDD run; this was partially supported, with the before-implementation share ranging from 26\% to 57\% across SDD runs, below the pilot values of 74\% and 82\%.

\textbf{RQ4 (Workflow Components).} H4a expected \texttt{sdd\_clarify} to resolve more open points as intended (tier~B) than \texttt{sdd}; this was not supported (Friedman $p = 0.91$), with \texttt{sdd\_clarify} scoring higher on only 2 of 5 tasks. H4b expected open points to be mostly resolved by assumption without clarification; this is consistent with the low tier~B scores across all conditions. H4c expected upstream artifacts to be rarely revised after planning; this was confirmed, with a median of 0 post-plan revisions. H4d expected SDD change requests to add a new feature specification and leave the original unedited; this held in 14 of 15 SDD CR runs.

\subsection{Comparison with Prior Work}

The tier~A ceiling is consistent with Rosa et al.'s finding that specification stages improve code quality only when the task is complex enough that prompting alone is insufficient~\cite{rosa}; the present tasks may be below that threshold. The partial tier~C improvement with \texttt{sdd\_secure} aligns with Marri's report of a 73\% reduction in security defects when CWE-derived constraints are written into the constitution~\cite{marri}, though the effect here is narrower: it appears only on tasks whose security risks the constitution explicitly addresses. This is a weaker form of Dhuri's finding that a specification frame cut checker findings from 148 to 23 across 250 task pairs~\cite{dhuri}, likely because Dhuri's frame stated security constraints explicitly while the present \texttt{sdd} and \texttt{sdd\_clarify} conditions do not.

The cost ratio (5--10$\times$ for SDD over unstructured) is higher than the pilot's 7$\times$ and larger than any cost figure reported in the SDD literature, though Grynets et al.~\cite{grynets} do not report time and Panda's study~\cite{panda} reports tokens but not wall-clock time. The before-implementation share (26--57\%) is lower than the pilot (74\%) and practice (82\%), suggesting that the pilot overestimated the specification cost because its single task had an unusually long specification phase.

The run-to-run variation in active time (up to 5{,}777~minutes for \texttt{sdd\_secure}) echoes Feng et al.'s observation that results varied widely with the system and model~\cite{feng} and Panda's finding that mandatory inline citations reduced output determinism~\cite{panda}. Functional scores were stable, but the agent's path was not.

\subsection{Implications for Practice}

For practitioners considering SDD with a capable coding agent on small, standard-library tasks: (1)~the specification workflow is unlikely to improve functional correctness, which is already near ceiling; (2)~writing security-specific constraints into the constitution can improve security outcomes, but only on tasks whose risks the constraints address---a generic constitution adds cost without measurable benefit; (3)~the cost of specification and planning is substantial (5--10$\times$ the time and tokens of unstructured prompting), and teams should weigh this against the value of the durable specification artifact itself; (4)~the clarification step did not reliably improve how the agent handles ambiguity, suggesting that the value of clarification may depend on the complexity and ambiguity of the task.

\subsection{Implications for Research}

Several open questions remain. First, the tier~A ceiling raises the question of where the threshold lies: at what task complexity does SDD begin to outperform unstructured prompting on correctness? A study with larger, framework-dependent tasks could answer this. Second, the security improvement was confined to tasks whose risks matched the constitution; whether a broader constitutional mandate (e.g., OWASP Top~10) can produce a broader effect is untested. Third, the large active-time variation within the same condition suggests that the agent's exploration strategy, not the specification, dominates cost; understanding and constraining that exploration is a research problem in its own right. Fourth, the before-implementation share was lower than expected, which may mean that the pilot's single task was unrepresentative or that specification cost scales sublinearly with task count. Finally, this study compared workflows but not the specifications they produce; a study of specification quality (using EPIC's ISO/IEC~29148 rubric~\cite{epic}) and its correlation with downstream outcomes would bridge that gap.

% ----------------------------------------------------------------------
% 10. THREATS TO VALIDITY
% ----------------------------------------------------------------------
\section{Threats to Validity}\label{sec:threats}

\textbf{Construct validity.}
\begin{itemize}[leftmargin=*]
    \item \emph{Security measured as an implicit expectation.} No task text mentions security, so tier C measures what an agent does unprompted. That is deliberate, but it is not the same as measuring how secure an agent can be when asked.
    \item \emph{Probe heuristics.} Thresholds such as minimum token lengths, and black-box checks such as salt detection, can misclassify. A race probe can miss a race, and the token probe judges a token by its length and alphabet only. Every probe failure is therefore confirmed by hand, and the manual review checks what the probes cannot see.
    \item \emph{Traceability partly built in.} The constitution prompt asks for testable requirements and the plan prompt for pytest, while no task text mentions tests, so the traceability measures partly reflect those prompts.
    \item \emph{The secure constitution and the probes share sources.} Both draw on OWASP and CWE, so \texttt{sdd\_secure} is told about the kinds of weakness the probes look for, though not about any probe.
\end{itemize}

\textbf{Internal validity.}
\begin{itemize}[leftmargin=*]
    \item \emph{Operator unblinded.} The Python runs are operated by the AI assistant that wrote the hidden tests. Its input is limited to fixed choices; every reply is an answer-sheet entry or a fixed fallback logged beside the message it answered, and the author reviews every classification. The remaining risk is in judging whether a turn is a question and which entry covers it.
    \item \emph{Fallback wording.} The mechanics checks showed that a fallback reply can change what the agent asks next. The replies were scoped to one question before the freeze. In the 15 valid runs closed by 14 November, 25 fallback replies were given, and in none did the agent ask the same question again (checked from \texttt{/speckit-clarify}'s question numbering and the next reply); within \texttt{/speckit-clarify} it moved to its next question each time. In all 48 valid runs, 62 fallback replies were given, and in none did the agent ask the same question again.
    \item \emph{Change requests depend on their build.} A weak build can make its change harder, so change-request outcomes are partly outcomes of the build; builds and changes are reported side by side.
    \item \emph{Carry-over.} Earlier run folders and the study repository share the workspace. The agent is never pointed to them, web tools are denied, and any access outside the run folder appears in the tool-call log.
    \item \emph{Agent latency} is included in active time and varies with API load; each run's start time is recorded so that time-of-day effects can be checked.
\end{itemize}

\textbf{External validity.}
\begin{itemize}[leftmargin=*]
    \item \emph{One harness and one model.} Results apply to Claude Code with \texttt{claude-opus-5}, not to SDD in general, and the tasks were drafted with an assistant from the same model family, which may suit that family's habits.
    \item \emph{Small, self-contained tasks.} The projects are 95--180 lines of reference code, standard library only, far smaller than most real systems.
    \item \emph{SDD without human review.} No one reviews or edits the generated specifications, so the results do not show what careful review would add, and SDD practised that way would cost more time.
\end{itemize}

\textbf{Conclusion validity.}
\begin{itemize}[leftmargin=*]
    \item \emph{Five tasks per condition.} No pairwise test can reach $p < 0.05$. Results are therefore worded by the pre-registered consistency rule, and a ceiling near 100\% on tier A is reported as a finding.
    \item \emph{One run per cell.} Model output varies between runs. The replicated project measures that variation for one task only.
\end{itemize}

\textbf{Researcher bias.} The author is researcher, product owner and coder. The tasks, answers, prompts, stopping rule, rubrics, analysis code and decision rules were fixed before any study run; the hidden tests were sealed with their hashes recorded; and the coding cannot be blinded to condition, because the specifications reveal it.

\textbf{Observed during the runs.}
\begin{itemize}[leftmargin=*]
    \item \emph{Interrupted sessions.} The account's five-hour usage limit and workspace restarts stopped eleven sessions mid-phase. Each was resumed in the same session with the fixed resume message, so the agent kept its context; logged active time includes the wait and is recomputed without idle gaps over 10 minutes.
    \item \emph{Harness version drift.} Claude Code was updated by the workspace during the study (2.1.318--2.1.325 instead of 2.1.317). Mitigation: versions recorded per run, later runs pinned to 2.1.317, results by version group reported as exploratory.
    \item \emph{Operator errors.} An operator helper matched its own prompt line and caused one wrong fallback (R007C), and a duplicated launch broke one run's log (R011C). Both were found by the audit of logged decisions; R011C was excluded and rerun, and the launch script now refuses to start a second copy of a running run.
\end{itemize}

% ----------------------------------------------------------------------
% 11. LIMITATIONS
% ----------------------------------------------------------------------
\section{Limitations}

This study was intentionally scoped to a single researcher, a small number of software tasks, a limited set of agent integrations, and a single knowledge domain for Part IV. It is not designed to produce a statistically generalizable claim about SDD's effectiveness in either domain. The Part IV comparison is structural and qualitative rather than a controlled experiment because SD-KDP and OpenKB were not designed as directly interchangeable tools.

Further limitations observed during execution:
\begin{itemize}[leftmargin=*]
    \item The schedule was compressed to 12 weeks, so each cell has one run except the replicated project, and Part IV runs alongside the software study.
    \item Only one agent harness is used, and Spec Kit's consistency check (\texttt{/speckit-analyze}) is held off in every condition, so its contribution to RQ4 is not measured.
    \item All tasks are small standard-library Python programs; the Java/Quarkus extension that would have checked another stack was dropped, so nothing is known about framework-heavy stacks.
    \item The runs' cost is reported from Claude Code's own estimates at API prices.
    \item The account's usage limit, not the agent, set the pace of data collection, so some sessions resumed hours or days after they stopped.
    \item The harness version was not held constant for the first 16 runs.
\end{itemize}

% ----------------------------------------------------------------------
% 12. CONCLUSION AND FUTURE WORK
% ----------------------------------------------------------------------
\section{Conclusion and Future Work}

This study compared four ways of directing a coding agent---unstructured prompting, Spec Kit's default SDD workflow, SDD with clarification, and SDD with constitutional security constraints---on five matched Python tasks, each followed by a change request. Functional correctness reached a ceiling in every condition, with no measurable benefit from specification. Security improved only when constitutional constraints directly addressed the task's security risks, and only on 2 of 5 tasks. The cost of SDD was 5--10 times that of unstructured prompting in time, tokens and human interaction, with specification and planning phases accounting for 26--57\% of the total. Specifications were rarely revised after they were written, and change requests did not alter the original specification. Run-to-run variation in active time was large, even when functional scores were stable. These results suggest that for small, well-understood tasks with a capable agent, the durable specification artifact is the primary benefit of SDD, not improved code quality. Constitutional security constraints show promise but need to be targeted to the specific risks present in the code.

Future work may include a multi-participant software study, a head-to-head shared-corpus quality comparison between SD-KDP and OpenKB, and further replication of large-scale SDD findings in controlled settings.

% ----------------------------------------------------------------------
% 13. REPRODUCIBILITY AND DATA AVAILABILITY
% ----------------------------------------------------------------------
\section{Reproducibility and Data Availability}\label{sec:repro}

All study materials are in a public repository: \url{https://github.com/Varshil25/spec-driven-development-study}. It holds the pre-registration (\texttt{docs/PREREGISTRATION.md}) and its Java addendum, the operator runbook, the task texts and change requests, the answer sheets, every fixed prompt, the study tools with their tests, the counterbalanced schedule, the base repository and every run as a git bundle, and each run's complete event log, diffs, specification snapshots and metrics (\texttt{logs/runs/}).

The hidden test suites, their reference implementations and their validation evidence are in the repository only in encrypted form (\texttt{sealed/}), with their SHA-256 hashes recorded in the pre-registration, and are published once the last study run is finished, so that anyone can check that the published suites are the ones fixed before any data existed.

\begin{table}[h]
\centering
\small
\caption{Environment.}\label{tab:env}
\begin{tabular}{@{}ll@{}}
\toprule
\textbf{Item} & \textbf{Value} \\
\midrule
Agent harness & Claude Code 2.1.317 as registered (R004--R011C: 2.1.318--2.1.323; R019C: 2.1.325), headless mode (\texttt{claude -p}) \\
Model & \texttt{claude-opus-5} \\
Spec Kit & 1.0.6, Claude Code integration, git extension \\
Run environment & Anthropic cloud workspace, Linux, Python 3.13.17 \\
Scoring & Python 3.13.17, pytest 9.1.1, Bandit 1.9.4 \\
Base repository & commit \texttt{c5bf438} (bundle \texttt{logs/bundles/base-v1.bundle}) \\
Seed & 20261023 (schedule, coding order, re-coding sample) \\
\bottomrule
\end{tabular}
\end{table}

\textbf{Data statement.} The tasks are synthetic and contain no personal data. Agents run in isolated workspaces with web tools denied. All literature is cited from its public source.

\textbf{AI assistance.} Claude, Anthropic's AI assistant, drafted study materials, tools and tests under the author's direction and operates the Python study runs as described in Section~\ref{sec:procedure}. The author reviewed the materials, approved every design decision, reviews every operator decision and is responsible for the content of this report.

\textbf{Freeze.} The pre-registration was frozen by merge commit \texttt{5a58b4f} on 4 November 2026, and the hashes were emailed to the advisor that day. The sealed suites were decrypted on 22 November 2026 after the last study run (R039C) closed. The tree hashes of both archives (builds and change requests) were verified against the hashes recorded in Section~11 of the pre-registration and matched.

% ----------------------------------------------------------------------
% REFERENCES
% ----------------------------------------------------------------------
\newpage
\section*{References}
\addcontentsline{toc}{section}{References}

\begin{thebibliography}{99}

\bibitem{alenezi}
M.~Alenezi. Specification-Driven Development as the Foundation of AI-Native Enterprise Software Engineering. arXiv:2607.16680, 2026. \url{https://arxiv.org/abs/2607.16680}

\bibitem{baltes}
S.~Baltes, F.~Angermeir, C.~Arora, M.~Mu\~noz Bar\'on, C.~Chen, L.~B\"ohme, F.~Calefato, N.~Ernst, D.~Falessi, B.~Fitzgerald, D.~Fucci, J.~He, C.~Treude, M.~Kalinowski, S.~Lambiase, D.~Russo, M.~Lungu, C.~Martinez Montes, L.~Prechelt, P.~Ralph, R.~van Tonder, and S.~Wagner. Guidelines for Empirical Studies in Software Engineering involving Large Language Models. arXiv:2508.15503, 2025. \url{https://arxiv.org/abs/2508.15503}

\bibitem{epic}
B.~Claudino, R.~Xing, Y.~Zuo, T.~Menezes, A.~Sarma, K.~Damevski, and Z.~Feng. The EPIC Framework for Spec-Driven Development. arXiv:2610.07534, 2026. \url{https://arxiv.org/abs/2610.07534}

\bibitem{dhuri}
S.~Dhuri. Specification Before Generation: A Pre-Registered, Five-Model Paired Evaluation of a Specification Frame for LLM-Generated Code in Money, Time, Idempotency, and Access Tasks. arXiv:2609.23270, 2026. \url{https://arxiv.org/abs/2609.23270}

\bibitem{feng}
S.~Feng, B.~Chen, B.~H.~Meyer, and G.~Mussbacher. LLM-Assisted Repository-Level Generation with Structured Spec-Driven Engineering. arXiv:2605.02455, 2026. \url{https://arxiv.org/abs/2605.02455}

\bibitem{speckit}
GitHub. Spec Kit, version 1.0.6. \url{https://github.com/github/spec-kit}

\bibitem{speckitblog}
GitHub. Spec-driven development with AI: Get started with a new open source toolkit. The GitHub Blog, 2025. \url{https://github.blog/ai-and-ml/generative-ai/spec-driven-development-with-ai-get-started-with-a-new-open-source-toolkit/}

\bibitem{grynets}
O.~Grynets, O.~Kaskun, A.~Salyk, D.~Zhuravchak, and V.~Lyashkevych. Specification-Driven Development Benchmark: Security Knowledge Transition. arXiv:2606.00167, 2026. \url{https://arxiv.org/abs/2606.00167}

\bibitem{marri}
S.~R.~Marri. Constitutional Spec-Driven Development: Enforcing Security by Construction in AI-Assisted Code Generation. arXiv:2602.02584, 2026. \url{https://arxiv.org/abs/2602.02584}

\bibitem{owasptop10}
OWASP Foundation. OWASP Top 10. \url{https://owasp.org/Top10/}

\bibitem{asvs}
OWASP Foundation. Application Security Verification Standard. \url{https://owasp.org/www-project-application-security-verification-standard/}

\bibitem{panda}
S.~Panda. Citation Discipline in Spec-Driven Development: A Cross-Model Empirical Study of Output Determinism and Automated Hallucination Detection in LLM-Generated Code. arXiv:2606.30689, 2026. \url{https://arxiv.org/abs/2606.30689}

\bibitem{pearce}
H.~Pearce, B.~Ahmad, B.~Tan, B.~Dolan-Gavitt, and R.~Karri. Asleep at the Keyboard? Assessing the Security of GitHub Copilot's Code Contributions. In \emph{2022 IEEE Symposium on Security and Privacy (SP)}, pages 754--768, 2022.

\bibitem{perry}
N.~Perry, M.~Srivastava, D.~Kumar, and D.~Boneh. Do Users Write More Insecure Code with AI Assistants? In \emph{Proceedings of the 2023 ACM SIGSAC Conference on Computer and Communications Security (CCS '23)}, pages 2785--2799, 2023.

\bibitem{rosa}
G.~Rosa, D.~Moreno-Lumbreras, G.~Robles, and J.~M.~Gonzalez-Barahona. Understanding Specification-Driven Code Generation with LLMs: An Empirical Study Design. Registered report, \emph{IEEE SANER 2026}. arXiv:2601.03878. \url{https://arxiv.org/abs/2601.03878}

\bibitem{openowls}
OpenOwls at Temple University. OpenOwls SD-KDP --- Spec-Driven Knowledge Distillation Process: Guide. 2026. \url{https://openowls-at-temple.github.io/openowls-sd-kdp-guide}. Accessed November 2026.

\bibitem{openkb}
VectifyAI. OpenKB: Open LLM Knowledge Base, powered by PageIndex. GitHub repository and README, Apache-2.0. \url{https://github.com/VectifyAI/OpenKB}. Accessed 14 November 2026.

\end{thebibliography}

% ----------------------------------------------------------------------
% APPENDIX
% ----------------------------------------------------------------------
\newpage
\appendix

\section{Validation Log}\label{app:log}

\begin{longtable}{@{}p{0.14\textwidth}p{0.28\textwidth}p{0.24\textwidth}p{0.26\textwidth}@{}}
\caption{Validation log. Instrument-level checks made before the study runs; results-level entries are added as they are completed.}\\
\toprule
\textbf{Date} & \textbf{Validation activity} & \textbf{Evidence location} & \textbf{Outcome} \\
\midrule
\endfirsthead
\toprule
\textbf{Date} & \textbf{Validation activity} & \textbf{Evidence location} & \textbf{Outcome} \\
\midrule
\endhead
2026-09-17 to 09-20 & Pilot run R001 with full instrumentation & \path{logs/runs/R001}, \path{docs/PILOT-REPORT.md} & Integrity 6/6; three instrument defects found and fixed before any study data \\
2026-10-23 & Practice suite (41 checks) frozen before either practice agent ran & \path{practice/T-LOGIN-01/FREEZE.txt} & Tree hash recorded; both builds scored; one rubric rule reworded and logged \\
2026-10-24 & Build suites (157 cases) validated against reference and naive code, then sealed & Pre-registration Appendix A; \path{sealed/README.md} & References 100\%; naive code tier A 96--100\%, tier C 0--70\% \\
2026-10-31 & Change-request suites (107 cases) reviewed, validated and sealed & Pre-registration Appendix C; \path{sealed/README.md} & References 107/107 on 3 runs; naive tier C 12/26; alternative implementation passes tiers A and C in 22 readings \\
2026-11-03 & Study tools tested & \path{tools/*/tests} & \path{sddlog} 80, run tool 20, analysis 15 tests pass \\
2026-11-03 & Mechanics checks R002 and R003 & \path{logs/runs/R002}, \path{R003}; \path{schedule/run-log.md} & Both pass all examples and integrity 6/6; one fallback-reply problem found \\
2026-11-04 & Pre-registration frozen and hashes sent to the advisor & Merge commit \path{5a58b4f}; pre-registration section 11 & Frozen before the first study run (R004) \\
2026-11-04 to 11-05 & Study runs R004, R004C, R005, R005C & \path{logs/runs/}; \path{schedule/run-log.md} & All pass the stopping rule and integrity 6/6; two interrupted sessions resumed with the fixed message \\
2026-11-09 to 11-10 & Study runs R006 to R008C (round 1 complete: 10 of 48 runs) & \path{logs/runs/}; \path{schedule/run-log.md} & All pass the stopping rule and integrity 6/6; three interrupted sessions resumed; active time recomputed for R006, R007, R007C \\
2026-11-10 to 11-14 & Study runs R009 to R011C (round 2) & \path{logs/runs/}; \path{schedule/run-log.md} & R009--R011 pass the stopping rule and integrity 6/6; R011C fails integrity (operator error), excluded and redone as R019C \\
2026-11-14 & Study runs R012 to R015C, R019C (round 3: 26 of 48 runs) & \path{logs/runs/}; \path{schedule/run-log.md} & All pass the stopping rule and integrity 6/6; Claude Code 2.1.317 pinned from R012 on \\
2026-11-16 to 11-21 & Study runs R016 to R039C (all 48 runs complete) & \path{logs/runs/}; \path{schedule/run-log.md} & All pass the stopping rule and integrity 6/6; 62 fallback replies across all 48 valid runs, none re-asked \\
2026-11-22 & Hidden suites unsealed; tree hashes checked & \path{sealed/README.md}; pre-registration Section~11 & Tree hashes of decrypted archives match pre-registration; all 48 runs scored with \texttt{score\_run.py} \\
2026-11-22 to 11-23 & Scoring, traceability coding and analysis & \path{coding/runs/}; \path{tools/study/analyze.py} & 73 score files; 379 traceability rows coded across 25 base runs; Tables~\ref{tab:builds}--\ref{tab:determinism} filled from \texttt{analyze.py} output \\
\bottomrule
\end{longtable}

\section{Artifact Inventory}

\begin{longtable}{@{}p{0.36\textwidth}p{0.56\textwidth}@{}}
\toprule
\textbf{Artifact} & \textbf{Location in the repository} \\
\midrule
\endfirsthead
\toprule
\textbf{Artifact} & \textbf{Location in the repository} \\
\midrule
\endhead
Pre-registration and Java addendum & \path{docs/PREREGISTRATION.md}, \path{docs/PREREGISTRATION-JAVA.md} \\
Operator runbook and logging protocol & \path{docs/RUNBOOK.md}, \path{docs/LOGGING-PROTOCOL.md} \\
Plain-language overview and weekly plan & \path{docs/STUDY-OVERVIEW.md}, \path{docs/WEEKLY-PLAN.md}, \path{weeks/} \\
Pilot report & \path{docs/PILOT-REPORT.md} \\
Task texts, change requests and worked examples & \path{tasks/} \\
Product-owner answer sheets & \path{operator/answer-sheets/} \\
Fixed prompts, including the secure constitution & \path{prompts/} \\
Logging instrument & \path{tools/sddlog/} \\
Run, scoring, coding and analysis tools & \path{tools/study/} \\
Schedule and run log & \path{schedule/schedule.csv}, \path{schedule/run-log.md} \\
Run logs: events, diffs, specification snapshots, metrics & \path{logs/runs/} \\
Base repository and run bundles & \path{logs/bundles/} \\
Sealed hidden suites (encrypted until the last run) & \path{sealed/} \\
Requirement register and coding sheets & \path{coding/} \\
Practice comparison & \path{practice/T-LOGIN-01/} \\
SAST reports & In each run's score file (\path{score_run.py --sast}) in each run's score JSON file under \texttt{scores/} \\
SD-KDP specifications and OpenKB outputs & \path{part-iv/} (specifications, corpus list, pipeline, tests, wiki) \\
\bottomrule
\end{longtable}

\end{document}
"""

GRID5_DATA = {
    ("T-REDACT-01", 0): [r"100\%", r"50\%", r"70\%", "3", "3"],
    ("T-REDACT-01", 1): [r"100\%", r"50\%", r"70\%", "3", "3"],
    ("T-REDACT-01", 2): [r"100\%", r"50\%", r"70\%", "3", "3"],
    ("T-REDACT-01", 3): [r"100\%", r"75\%", r"100\%", "0", "0"],
    ("T-TARX-01", 0): [r"100\%", r"100\%", r"100\%", "0", "0"],
    ("T-TARX-01", 1): [r"100\%", r"67\%", r"100\%", "0", "0"],
    ("T-TARX-01", 2): [r"100\%", r"67\%", r"100\%", "0", "0"],
    ("T-TARX-01", 3): [r"100\%", r"67\%", r"100\%", "0", "0"],
    ("T-BOOKMARKS-01", 0): [r"100\%", r"0\%", r"88\%", "1", "1"],
    ("T-BOOKMARKS-01", 1): [r"100\%", r"0\%", r"88\%", "1", "1"],
    ("T-BOOKMARKS-01", 2): [r"100\%", r"33\%", r"88\%", "1", "1"],
    ("T-BOOKMARKS-01", 3): [r"100\%", r"0\%", r"88\%", "1", "1"],
    ("T-ACCOUNTS-01", 0): [r"100\%", r"33\%", r"100\%", "0", "0"],
    ("T-ACCOUNTS-01", 1): [r"100\%", r"33\%", r"100\%", "0", "0"],
    ("T-ACCOUNTS-01", 2): [r"100\%", r"33\%", r"100\%", "0", "0"],
    ("T-ACCOUNTS-01", 3): [r"100\%", r"33\%", r"100\%", "0", "0"],
    ("T-PASTE-01", 0): [r"100\%", r"33\%", r"83\%", "2", "1"],
    ("T-PASTE-01", 1): [r"100\%", r"33\%", r"83\%", "1", "1"],
    ("T-PASTE-01", 2): [r"100\%", r"67\%", r"83\%", "1", "1"],
    ("T-PASTE-01", 3): [r"96\%", r"33\%", r"100\%", "0", "0"],
}

GRID4_DATA = {
    ("T-REDACT-01", 0): [r"100\%", r"67\%", r"92\%", "3"],
    ("T-REDACT-01", 1): [r"100\%", r"67\%", r"92\%", "3"],
    ("T-REDACT-01", 2): [r"100\%", r"78\%", r"92\%", "2"],
    ("T-REDACT-01", 3): [r"100\%", r"89\%", r"100\%", "1"],
    ("T-TARX-01", 0): [r"100\%", r"100\%", r"100\%", "0"],
    ("T-TARX-01", 1): [r"100\%", r"100\%", r"100\%", "0"],
    ("T-TARX-01", 2): [r"100\%", r"100\%", r"100\%", "0"],
    ("T-TARX-01", 3): [r"100\%", r"100\%", r"100\%", "0"],
    ("T-BOOKMARKS-01", 0): [r"100\%", r"100\%", r"96\%", "0"],
    ("T-BOOKMARKS-01", 1): [r"100\%", r"100\%", r"96\%", "0"],
    ("T-BOOKMARKS-01", 2): [r"100\%", r"100\%", r"96\%", "0"],
    ("T-BOOKMARKS-01", 3): [r"100\%", r"100\%", r"96\%", "0"],
    ("T-ACCOUNTS-01", 0): [r"100\%", r"100\%", r"100\%", "0"],
    ("T-ACCOUNTS-01", 1): [r"100\%", r"100\%", r"100\%", "0"],
    ("T-ACCOUNTS-01", 2): [r"100\%", r"100\%", r"100\%", "0"],
    ("T-ACCOUNTS-01", 3): [r"100\%", r"100\%", r"100\%", "0"],
    ("T-PASTE-01", 0): [r"100\%", r"100\%", r"97\%", "1"],
    ("T-PASTE-01", 1): [r"100\%", r"100\%", r"97\%", "0"],
    ("T-PASTE-01", 2): [r"100\%", r"100\%", r"97\%", "0"],
    ("T-PASTE-01", 3): [r"100\%", r"100\%", r"97\%", "0"],
}

GRID3_DATA = {
    ("T-REDACT-01", 0): [r"30", r"80\%", r"0\%"],
    ("T-REDACT-01", 1): [r"30", r"87\%", r"100\%"],
    ("T-REDACT-01", 2): [r"45", r"87\%", r"100\%"],
    ("T-REDACT-01", 3): [r"30", r"93\%", r"100\%"],
    ("T-TARX-01", 0): [r"13", r"100\%", r"0\%"],
    ("T-TARX-01", 1): [r"13", r"92\%", r"100\%"],
    ("T-TARX-01", 2): [r"13", r"92\%", r"100\%"],
    ("T-TARX-01", 3): [r"13", r"92\%", r"100\%"],
    ("T-BOOKMARKS-01", 0): [r"14", r"79\%", r"0\%"],
    ("T-BOOKMARKS-01", 1): [r"14", r"79\%", r"100\%"],
    ("T-BOOKMARKS-01", 2): [r"14", r"86\%", r"100\%"],
    ("T-BOOKMARKS-01", 3): [r"14", r"79\%", r"100\%"],
    ("T-ACCOUNTS-01", 0): [r"18", r"86\%", r"0\%"],
    ("T-ACCOUNTS-01", 1): [r"18", r"89\%", r"100\%"],
    ("T-ACCOUNTS-01", 2): [r"18", r"89\%", r"100\%"],
    ("T-ACCOUNTS-01", 3): [r"18", r"89\%", r"94\%"],
    ("T-PASTE-01", 0): [r"16", r"88\%", r"0\%"],
    ("T-PASTE-01", 1): [r"16", r"88\%", r"100\%"],
    ("T-PASTE-01", 2): [r"16", r"94\%", r"100\%"],
    ("T-PASTE-01", 3): [r"16", r"81\%", r"100\%"],
}

tex = tex.replace("GRID5", grid(5, GRID5_DATA)).replace("GRID4", grid(4, GRID4_DATA)).replace("GRID3", grid(3, GRID3_DATA)).replace("GRIDTIME", grid(4, TIME))
(HERE / "final-report.tex").write_text(tex)
print("wrote", HERE / "final-report.tex")
