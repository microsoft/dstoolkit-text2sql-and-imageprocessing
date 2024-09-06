# Multi-Shot Text2SQL Component

This portion of the repo contains code for linking Azure Document Intelligence with AI Search to process complex documents with charts and images, and uses multi-modal models (gpt4o) to interpret and understand these.

The implementation in Python, although it can easily be adapted for C# or another language.

The sample provided works with Azure SQL Server, although it has been easily adapted to other SQL sources such as Snowflake.

## High Level Workflow

The following diagram shows a comparison of a common indexing approach.

![High level workflow for indexing with Azure Document Intelligence based skills](./images/Indexing%20vs%20Indexing%20with%20ADI.png "Indexing with Azure Document Intelligence Approach")
