# AI Complaint Classification Lab

AI Complaint Classification Lab is a Streamlit classroom app for MBA students. Students upload a synthetic complaint dataset and a taxonomy workbook, write a classification prompt, test the prompt on a small sample, run the full classification with OpenAI models, review the outputs, and export the classified file for submission.

This V1 app is intentionally scoped for classroom use:

- OpenAI only
- No instructor answer-key upload
- No scoring workflow
- No user accounts
- No database
- No stored API keys

## Local setup

1. Create and activate a Python 3.9+ environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Optionally create a local `.env` file:

```bash
cp .env.example .env
```

4. Add your OpenAI key to `.env` or paste it into the app sidebar at runtime.
5. Start the app:

```bash
streamlit run app.py
```

## Streamlit Community Cloud notes

- The app is designed to run without Streamlit secrets.
- Students can paste their OpenAI API key directly into the sidebar.
- Instructors can also configure an environment variable named `OPENAI_API_KEY` if they prefer.
- Only the dependencies in `requirements.txt` are required for deployment.

## Required complaint dataset columns

The uploaded complaint dataset must contain all of these columns:

- `complaint_id`
- `received_date`
- `channel`
- `product`
- `region`
- `customer_segment`
- `complaint_text`
- `visible_context`

The app accepts CSV or Excel files. For Excel workbooks with multiple sheets, the app recommends the first sheet with all required columns and also lets the user choose a sheet manually.

## Required taxonomy workbook sheets

The uploaded taxonomy workbook must be an Excel file with all of these sheets:

- `Categories`
- `Root_Causes`
- `Severity_Rules`
- `Escalation_Rules`

### Required columns by sheet

`Categories`

- `category`
- `definition`
- `examples`
- `non_examples`

`Root_Causes`

- `root_cause`
- `definition`
- `examples`
- `non_examples`

`Severity_Rules`

- `severity`
- `definition`
- `examples`

`Escalation_Rules`

- `escalation_flag`
- `definition`
- `examples`

## API key handling

- The sidebar uses a password-style input for the OpenAI API key.
- The app can also load `OPENAI_API_KEY` from a local `.env` file.
- The app does not save or log the API key.
- There is a built-in “Test API connection” button for quick validation.

## Workflow

1. Enter an OpenAI API key.
2. Select a model from the built-in model list.
3. Upload the complaint dataset.
4. Upload the taxonomy workbook.
5. Write or refine the classification prompt.
6. Run the 5-record test sample.
7. Run the full classification.
8. Review outputs and export CSV or Excel.

## Reliability features

- Backend-controlled batching
- Structured JSON schema enforcement
- Retry logic for API calls
- Malformed JSON repair attempt
- Per-batch failure handling
- Partial results retained even if some rows fail
- Friendly user-facing validation errors
- Technical details hidden behind expanders

## Known limitations

- The app depends on live OpenAI API access.
- Classification quality depends on the uploaded taxonomy, selected model, and student-written prompt.
- The app does not compare results to an instructor key.
- V1 supports only OpenAI models and text-based classification.

