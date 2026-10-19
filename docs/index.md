---
layout: home
title: Alloq developer docs
description: Start page of the Alloq developer documentation, with what Alloq is, who uses it, how the docs are organised and how the stories link to the code.
source_paths:
  - README.md
last_verified_commit: "cb9d5b0 (v2.0.4)"

hero:
  name: Alloq
  text: Developer documentation
  tagline: Resource management & capacity planning for software teams
  actions:
    - theme: brand
      text: Get started
      link: /guide/getting-started
    - theme: alt
      text: Story map
      link: /features/story-map

features:
  - title: Guide
    details: Set up a local environment, run the app and change the code the way the project expects.
    link: /guide/getting-started
  - title: Architecture
    details: Read how the packages, layers, data model, access rules, calculations and the desktop app fit together.
    link: /architecture/overview
  - title: Features
    details: Start at the story map and read the user stories of each feature with links to the code and the tests.
    link: /features/story-map
  - title: Reference
    details: Look up the Task commands, the configuration keys, the test setup and the domain terms.
    link: /reference/commands
---

## What Alloq is

Alloq is a web app that helps a software team plan which people work on which project in each week. It counts the free capacity of each person after absences, public holidays, part time and internal work. It also shows the state of all projects on one page. Alloq runs in the browser, and there is also a macOS desktop app that works on the same central database.

## Who uses Alloq

Alloq has four personas:

- **Administrator.** An administrator decides who can sign in and what each person may read or change. The administrator also keeps the roles, daily rates, departments and public holidays.
- **Project manager.** A project manager plans people on projects week by week and keeps the data, status and risks of each project current.
- **Employee.** An employee reads the planning and the projects without changing them and keeps their own account up to date.
- **Desktop user.** A desktop user works in the macOS app and signs in with a Microsoft account.

The [story map](/features/story-map) describes the goals of each persona in more detail.

## How the docs are organised

The docs follow the Diátaxis model, which sorts pages by what the reader wants to do. There are four sections:

- **Guide.** These pages show you how to set up Alloq and how to contribute a change.
- **Architecture.** These pages explain how Alloq is built and why.
- **Features.** The story map lists all user stories by activity. Each feature page holds the stories of one part of the app.
- **Reference.** These pages list the commands, the configuration, the test setup and the glossary, so you can look up a single fact.

## How the stories link to the code

Each user story has acceptance criteria and an Evidence block. The Evidence block links to the files and names the functions, states or classes that implement the story. When a criterion has no test that checks it, the criterion ends with "(no test)". When the code does not answer a question about the behaviour, the story lists it under "Open questions" instead of guessing.

Links to code open the file on GitHub on the branch `main`. The docs were checked against the commit cb9d5b0 (v2.0.4). If the code changed after that commit, a page can be out of date.

## For AI agents

The file [llms.txt](/llms.txt) lists every page with its path and a one line description. It is in `docs/public/llms.txt`, and the site serves it at `/llms.txt`.
