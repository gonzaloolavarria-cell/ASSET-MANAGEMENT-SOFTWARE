# Feature Spec: Field Capture System

## Context

Maintenance technicians spend most of their time in the field and need a fast way to report equipment failures.

## Goal

Enable fault reporting using voice, photo, or text in less than 60 seconds.

## Functional Requirements

Capture voice input
Convert speech to text
Capture equipment photos
Analyze images for anomalies
Structure captured data into a work request

## Technical Requirements

Speech recognition (Whisper or Deepgram)
Image analysis (Claude Vision)
Mobile UI

## Data Model

WorkRequest
ImageAttachment
AudioAttachment

## API

POST /field-capture

input
audio
image
text
asset_tag

output
structured_work_request
failure_mode
priority

## Acceptance Criteria

capture time < 60 seconds
speech accuracy > 90%
