#!/usr/bin/env python3
from pydevice import DeviceMagic
import json
import base64

dm1_args = {'org_id': '185280',
            'api_key': 'Basic RWtuSG9GelVWNkZ2aWZ2a1lZS3c6eA=='}

dm2_args = {'org_id': '185280',
            'api_key': 'Basic RWtuSG9GelVWNkZ2aWZ2a1lZS3c6eA=='}

dm1 = DeviceMagic(dm1_args)  # Account 1
dm2 = DeviceMagic(dm2_args)  # Account 2


def clone_resource_second_org(base_id, base_details, second_org):
    file = dm1.resource.download(base_id)
    encoded_file = base64.b64encode(file).decode('utf-8')
    mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    description = base_details['resource']['description']
    filename = base_details['resource']['original_filename']
    return second_org.resource.create(description, filename,
                                      encoded_file, mime)


def merge_content(base_id, second_org):
    base_details = dm1.resource.details(base_id)
    clone_details = clone_resource_second_org(
        base_id, base_details, second_org)
    clone_filename = clone_details['resource']['original_filename']
    print("Resource clone created: {}".format(clone_filename))
    clone_id = clone_details['resource']['id']
    base_identifier = base_details['resource']['identifier']
    clone_identifier = clone_details['resource']['identifier']
    base_summary = base_details['resource']['generated_content_summary']
    clone_summary = clone_details['resource']['generated_content_summary']
    linked_content = {'columns': [], 'tables': []}
    linked_content['id'] = (base_id, clone_id)
    linked_content['identifier'] = (base_identifier, clone_identifier)

    for t_index, t_data in enumerate(base_summary):
        base_table = base_summary[t_index]['table_id']
        clone_table = clone_summary[t_index]['table_id']
        linked_content['tables'].append((base_table, clone_table))
        for c_index, c_data in enumerate(base_summary[t_index]['columns']):
            base_columns = \
                base_summary[t_index]['columns'][c_index]['column_id']
            clone_columns = \
                clone_summary[t_index]['columns'][c_index]['column_id']
            linked_content['columns'].append((base_columns, clone_columns))

    return linked_content


def match_resource(
        question, index, resource_ids,
        fetched_resources, second_org):
    options_resource = question["options_resource"]
    for id in resource_ids[index:]:
        resource = dm1.resource.details(id)['resource']
        if resource['identifier'] == options_resource:
            print("Resource located")
            content = merge_content(id, second_org)
            fetched_resources[resource['identifier']] = \
                {"id": id, "content": content}
            index += 1
            link_cloned_resource(
                question, fetched_resources[options_resource]['content'])
            break
        else:
            fetched_resources[resource['identifier']] = {"id": id}
            index += 1
    return index


def find_match(question_piece, content):
    match = None
    for item in content:
        if question_piece == item[0]:
            match = item[1]
            break
    return match


def link_cloned_resource(question, content):
    question['options_resource'] = content['identifier'][1]
    question['options_table'] = \
        find_match(question['options_table'], content['tables'])
    question['options_text_column'] = \
        find_match(question['options_text_column'], content['columns'])
    question['options_identifier_column'] = \
        find_match(question['options_identifier_column'], content['columns'])
    if 'options_filter_expr' in question.keys():
        filter_expression = question['options_filter_expr']
        for column in content['columns']:
            filter_expression = filter_expression.replace(column[0], column[1])
        question['options_filter_expr'] = filter_expression
    print("Question successfully linked to resource\n")


def link_select_question(section, fetched_resources, second_org):
    options_resource = section["options_resource"]
    if "content" in fetched_resources[options_resource]:
        content = fetched_resources[options_resource]['content']
        link_cloned_resource(section, content)
    else:
        id = fetched_resources[options_resource]['id']
        content = merge_content(id, second_org)
        fetched_resources[options_resource]['content'] = content
        link_cloned_resource(
            section, fetched_resources[options_resource]['content'])


def replace_select_questions(
        sections, resource_ids, index,
        fetched_resources, second_org):
    for section in sections:
        type = section["type"]
        if "children" in section.keys():
            replace_select_questions(section["children"], resource_ids, index,
                                     fetched_resources, second_org)
        elif type == "select" and "options_resource" in section.keys():
            print(
                "Replacing resource in question - {}".format(section['title']))
            if section["options_resource"] in fetched_resources.keys():
                link_select_question(section, fetched_resources, second_org)
            else:
                print("Searching for resource...")
                index = match_resource(section, index, resource_ids,
                                       fetched_resources, second_org)
        else:
            continue
    return sections


def main():
    resources = dm1.resource.all()['resources']  # Fetch all resources ids
    resource_ids = []
    for resource in resources:
        resource_ids.append(resource['id'])

    print("Resource id's copied from organizations...\n")

    data = dm1.form.details(9965660)  # Retrieve form definition from Account 1
    fetched_resources = {}
    index = 0
    data["children"] = replace_select_questions(data["children"], resource_ids,
                                                index, fetched_resources, dm2)
    cloned_form = json.dumps(data)

    form = dm2.form.create(cloned_form)  # Create form in Account 2
    print("Form created: {}".format(form['name']))


if __name__ == "__main__":
    main()
