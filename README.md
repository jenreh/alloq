# Project Template Setup Guide

This repository serves as a template for creating new projects. Follow the steps below to set up your project.

## Prerequisites

Ensure the following tools are installed on your system:

1. **uv**: Used for managing dependencies and running tasks. [Install uv](https://docs.astral.sh/uv/getting-started/installation/).
2. **task**: A task runner for automating project setup and management. [Install task](https://taskfile.dev/docs/installation).

## Setup Instructions

1. **Create a Database**
   - Set up a new database for your project. Ensure you have the necessary credentials and permissions.

2. **Copy Environment Variables File**
   - Copy the `.env.default` file to `.env`:

     ```bash
     cp .env.default .env
     ```

   - Open the `.env` file and set the appropriate values for your environment.

3. **Initialize the Project**
   - Run the following command to initialize the project:

     ```bash
     task init
     ```

This will set up the necessary dependencies, configurations, and database migrations for your project.
