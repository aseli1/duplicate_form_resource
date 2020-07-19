# duplicate_form_resource
Account management tool which duplicates forms and resources across organizations in Device Magic. This tool utilizes [pydevice](https://github.com/aseli1/pydevice).

Supports:
[Select questions](https://docs.devicemagic.com/en/articles/392920-select-options-from-a-resource),
[Attached files](https://docs.devicemagic.com/en/articles/392966-attached-file), and [Calculated questions](https://docs.devicemagic.com/en/articles/392923-lookup-function-for-calculated-questions)

## Installation

Clone or download the zip file and extract manually.

Install requirements
```python
pip3 install -r requirements.txt
```

## Usage

Navigate to the directory where the script exists. Open the `duplicate_form_resource.py` file and edit `dm_one_args` and `dm_two_args` variables with the required organization details. For more information on these values and how they're utilized, see [here](https://github.com/aseli1/pydevice).

Next, edit the `form_ids` variable to include the form id's of the forms you'd like to copy from `dm_one` to `dm_two`. These values can be captured using the methods described in this [article](https://docs.devicemagic.com/en/articles/392940-forms-api).

Run the script with the command `python3 duplicate_form_resource.py`.
