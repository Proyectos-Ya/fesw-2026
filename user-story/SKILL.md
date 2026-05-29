---
name: user-story
description: Use when you need to create, edit or analyze user histories.
---

# User story Generator

## User story

Every User story must be doable by a single developer in a single sprint (5 days). Also, the crud operations in UH language must be separated in different user stories: visualize, create, update/edit, delete.

The user story should be generated in Markdown format with the following structure:

# HU-001: story title

## Description

Me, as a [User Role], I want to [User Goal], so that [User Benefit].

## Conversation

Ideas, thoughts, feelings, opinions, preferences, ocurred during the conversation with the user.

## Acceptance Criteria

Detailed steps to achieve the user story. Each step must be an interaction between the user and the system. The acceptance criteria must be a step by step navigation through the application. Always assume the user is using the last view presented to him. Consider Edge cases. Also specify the ui styles, for example, a select input, a tab view, a modal form, a list, a table, etc.

Follow strictly the following format for each criteria:

- Given a [User role] in a [Context (Navigation step, UI state, etc)], when [User Action (user interaction with ui)], then [User Result (system response, ui response state)].

Make a minimum of 3 acceptance criteria for each user story, unless it is a very simple or obvious user story, in that case analyze the option of asking the user if combining 2 or more user histories will make more sense. Try to make as many acceptance criteria as navigation steps are required to perform the user action and how the system should react to each user action. Also make sure that the acceptance criteria are not redundant and cover all the possible edge cases.

## Quick example:

If you are making a user story to post data vía forms, the acceptance criteria should answer:

1. Where is the user (in the navigation) when he want's to post the data?
2. Wich elements the user needs to click or interact on to deploy/reveal/open the form to post data?
3. What data the user needs to provide to post the data?
4. Wich elements are provided to fill in the data? (text input, dropdown select, autocomplete, date picker, checkbox, radio buttons, textarea, file upload, etc.)
5. Wich element the user needs to click or interact on to submit the data?
6. What the system does after the data submission (when the user clicks on the submit button)?

# Complete example

### HU-001: Visualize events

#### Description

Me, as a student, I want to visualize my events, so that I can see my schedule.

#### Conversation

No conversation is needed for this user story. but if the client wants to add more details, it is allowed.

#### Acceptance Criteria

Example (NOTE: This is only an example, dont use it directly in the context of the user using this skill. The goal of this example is to show how to create acceptance criteria for this skill.):

- Given a student authenticated in the system, when the student visits the main page, then the system shows an Events tab.

(NOTE: in this acceptance criteria, indicate just the steps to complete the objective of the HU, not the steps to complete other HUs. In this case the HU is visualize events, so the acceptance criteria should be about visualize events, not about creating, updating or deleting events or other features and it should start from the initial state after authentication in the system.)

- Given a student in the main page, when the student clicks on the "Events" tab, then the system navigates to the events page.
- Given a student authenticated in the system, when the student visits the events page, then the system shows the events organized by date in a list view and shows the button "Calendar View".
- Given a student in the events page, when the student clicks on the "Calendar View" tab, then the system shows a calendar with the events in their cell.

# Order of user histories and dependency rules

The user histories must start with the most important core functionality and should be ordered by priority. Do not generate user histories in any other order.

Generate the user stories in the following order:

1. Core business flows
2. Core visualization flows
3. Core creation flows
4. Core update flows
5. Core deletion flows
6. Secondary business operations
7. Administrative operations
8. Reports and exports
9. Notifications
10. Optional enhancements

A user story can only depend on previously generated stories.

Always identify:

- Navigation dependencies
- Authentication dependencies
- Data dependencies
- Permission dependencies

# Story points

For each UH, assign the number of story points based on the complexity of the user story. Make sure that the story points are not redundant and cover all the possible edge cases. Also make sure that the story points are not overlapping and cover all the possible edge cases.

## Story points ranges

- 1 story point: up to 2 hours
- 2 story points: up to 4 hours
- 3 story points: up to 1 day
- 5 story points: up to 3 days
- 8 story points: up to a 5 days
- 13 story points: more than 5 days - AVOID MORE THAN 8 STORY POINTS
- 21 story points: 2 weeks - AVOID MORE THAN 8 STORY POINTS

# Definition of Ready

Before generating a user story, validate that the following information exists:

- User role
- Business objective
- Functional scope
- Navigation context
- Main action
- Expected result
- Business rules
- Restrictions or validations
- Dependencies with other modules

If any critical information is missing, ask for clarification before generating the story.

# Story Splitting Rules

A user story must represent a single functional objective.

Always split user stories when they involve:

- Different user roles
- Different navigation flows
- Different business rules
- Different permissions
- Different states
- Different integrations
- Different data sources
- Different UI patterns
- Bulk operations
- File uploads
- Notifications
- Reports
- Imports or exports
- Search/filter/sort operations
- Pagination
- Mobile-specific behavior
- Admin functionality

Never combine:

- Visualization + mutation operations
- Configuration + operational flows
- Synchronous + asynchronous processes
- Manual + automated actions

# Non Functional Restrictions

Do not generate:

- Technical tasks
- Infrastructure tasks
- Backend implementation tasks
- Database tasks
- DevOps tasks
- Refactoring tasks
- Internal architecture tasks

Only generate user-centered business stories.

A user story must:

- Be completable in at most 3 development days
- Require only one primary business objective
- Avoid parallel subflows
- Avoid multiple independent validations

# Acceptance Criteria Rules

Acceptance criteria must:

- Describe observable behavior
- Be testable
- Avoid implementation details
- Avoid ambiguous wording
- Use explicit UI interactions
- Include validations and restrictions
- Include empty states when applicable
- Include loading/error states for async actions

Do not use:

- "correctly"
- "properly"
- "appropriately"
- "efficiently"
- "user friendly"

Acceptance criteria must include:

- Success flow
- Validation flow
- Empty state
- Error state when applicable

# UI Consistency Rules

Reuse existing UI patterns whenever possible.

Prefer:

- Tables for large datasets
- Cards for summarized information
- Modal forms for short forms
- Dedicated pages for large forms
- Tabs only when multiple contextual sections exist

Avoid:

- Nested modals
- Multiple primary actions
- Hidden critical actions

# Output Rules

Do not generate introductions, explanations or summaries outside the markdown structure.

Output must always be valid markdown.

# Languages

This skill supports English and Spanish.

So, the formulas in acceptance criteria must be in the same language as the user story.

Example:

- If the user story is in English, the formulas must be in English (As a [user], I want to [action], so that [result]. Given [context], when [action], then [result].)
- If the user story is in Spanish, the formulas must be in Spanish (Como [usuario], quiero [acción], para [resultado]. Dado [contexto], cuando [acción], entonces [resultado].)
