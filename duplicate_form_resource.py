#!/usr/bin/env python3
from pydevice import DeviceMagic
import logging
import json
import base64
import magic
import re


def clone_resource(base_id, base_details, first_org, second_org):
    file = first_org.resource.download(base_id)
    mime = magic.from_buffer(file, mime=True)
    encoded_file = base64.b64encode(file).decode('utf-8')
    description = base_details['resource']['description']
    filename = base_details['resource']['original_filename']
    return {'dm_response': second_org.resource.create(description, filename,
                                                      encoded_file, mime),
            'mime': mime}


def merge_clone_with_original(original_id, first_org, second_org):
    original_details = first_org.resource.details(original_id)
    clone_details = clone_resource(
        original_id, original_details, first_org, second_org)
    clone_mime = clone_details['mime']
    clone_dm_attributes = clone_details['dm_response']
    clone_filename = \
        clone_dm_attributes['resource']['original_filename']
    logging.info('Resource clone created: {}'.format(clone_filename))
    clone_id = clone_dm_attributes['resource']['id']
    base_identifier = original_details['resource']['identifier']
    clone_identifier = clone_dm_attributes['resource']['identifier']
    linked_content = {'columns': [], 'tables': []}
    linked_content['id'] = (original_id, clone_id)
    linked_content['identifier'] = (base_identifier, clone_identifier)
    xlsx_mime = \
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    if clone_mime == xlsx_mime:
        base_summary = \
            original_details['resource']['generated_content_summary']
        clone_summary = \
            clone_dm_attributes['resource']['generated_content_summary']
        merge_resource_summaries(base_summary, clone_summary, linked_content)
    return linked_content


def merge_resource_summaries(base_summary, clone_summary, linked_content):
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


def fetch_replace_resource(question, index, resource_ids,
                           fetched_resources, first_org, second_org):
    resource_identifier = question[identifier_key(question)]
    for id in resource_ids[index:]:
        resource = first_org.resource.details(id)['resource']
        if resource['identifier'] == resource_identifier:
            logging.info('Resource located')
            content = merge_clone_with_original(id, first_org, second_org)
            fetched_resources[resource['identifier']] = \
                {'id': id, 'content': content}
            index += 1
            return question_linked_to_clone(
                question, fetched_resources[resource_identifier]['content'])
        else:
            fetched_resources[resource['identifier']] = {"id": id}
            index += 1


def find_match(identifier, merged_details):
    match = None
    for pair in merged_details:
        if identifier == pair[0]:
            match = pair[1]
            break
    return match


def replace_select_bindings(question, merged_details):
    question['options_resource'] = merged_details['identifier'][1]
    question['options_table'] = \
        find_match(question['options_table'], merged_details['tables'])
    question['options_text_column'] = \
        find_match(question['options_text_column'], merged_details['columns'])
    question['options_identifier_column'] = \
        find_match(
            question['options_identifier_column'], merged_details['columns'])
    if 'options_filter_expr' in question.keys():
        filter_expression = question['options_filter_expr']
        for column in merged_details['columns']:
            filter_expression = filter_expression.replace(column[0], column[1])
        question['options_filter_expr'] = filter_expression


def replace_calculated_bindings(question, merged_details):
    question['resource_identifier'] = merged_details['identifier'][1]
    question['resource_table'] = \
        find_match(question['resource_table'], merged_details['tables'])
    question['key_column'] = \
        find_match(question['key_column'], merged_details['columns'])
    question['value_column'] = \
        find_match(question['value_column'], merged_details['columns'])
    logging.info('Question successfully linked to resource')


def question_linked_to_clone(question, merged_details):
    if question['type'] == 'resource':
        question['resource_identifier'] = merged_details['identifier'][1]
    if question['type'] == 'select':
        replace_select_bindings(question, merged_details)
    if question['type'] == 'calculated':
        replace_calculated_bindings(question, merged_details)
        return format_lookup_expression(question)
    logging.info('Question successfully linked to resource')


def locate_resource_link_question(section, fetched_resources,
                                  first_org, second_org):
    resource_identifier = section[identifier_key(section)]
    if 'content' in fetched_resources[resource_identifier]:
        content = fetched_resources[resource_identifier]['content']
        return question_linked_to_clone(section, content)
    else:
        id = fetched_resources[resource_identifier]['id']
        content = merge_clone_with_original(id, first_org, second_org)
        fetched_resources[resource_identifier]['content'] = content
        return question_linked_to_clone(
            section, fetched_resources[resource_identifier]['content'])


def identifier_key(question):
    if question['type'] == 'select':
        return 'options_resource'
    elif question['type'] == 'resource':
        return 'resource_identifier'
    elif question['type'] == 'calculated':
        return 'resource_identifier'
    else:
        raise ValueError('Invalid question type: {}'.format(question['type']))


def format_lookup_expression(resource_data):
    return "\"{0}\",\"{1}\",\"{2}\",\"{3}\"".format(
        resource_data['resource_identifier'], resource_data['resource_table'],
        resource_data['key_column'], resource_data['value_column'])


def generate_question(type, content_summary):
    return {'type': type,
            'resource_identifier': content_summary[0],
            'resource_table': content_summary[1],
            'key_column': content_summary[2],
            'value_column': content_summary[3]}


def replace_calculated_expression(section, fetched_resources, resource_ids,
                                  first_org, second_org, index):
    lookup_occurrences = \
        re.findall(r'LOOKUP\([^)]+\)', section['calculate_expr'])
    if len(lookup_occurrences) > 0:
        logging.info(
            "Replacing calculated expression in question \"{}\"".format(
                section['title']))
        resource_pairs = []
        for lookup in lookup_occurrences:
            bindings = re.findall(r'"(.*?)"', lookup)
            lookup_question = generate_question(section['type'], bindings)
            original_expression = \
                format_lookup_expression(lookup_question)
            clone_expression = replace_question_resource(
                lookup_question, index, resource_ids,
                fetched_resources, first_org, second_org)
            resource_pairs.append((original_expression, clone_expression))
        for pair in resource_pairs:
            section['calculate_expr'] = \
                section['calculate_expr'].replace(pair[0],
                                                  pair[1])


def replace_question_resource(section, index, resource_ids,
                              fetched_resources, first_org, second_org):
    if section[identifier_key(section)] in fetched_resources.keys():
        question = locate_resource_link_question(
            section, fetched_resources,
            first_org, second_org)
    else:
        logging.info('Searching for resource...')
        question = fetch_replace_resource(
            section, index, resource_ids,
            fetched_resources, first_org, second_org)
    return question


def clone_replace_resources(elements, resource_ids, index,
                            fetched_resources, first_org, second_org):
    for element in elements:
        type = element['type']
        if 'children' in element.keys():
            clone_replace_resources(element['children'], resource_ids, index,
                                    fetched_resources, first_org, second_org)
        elif type == 'select' and 'options_resource' in element.keys():
            logging.info(
                'Replacing resource in question \'{}\''.format(
                    element['title']))
            replace_question_resource(element, index, resource_ids,
                                      fetched_resources, first_org, second_org)
        elif type == 'resource':
            logging.info(
                'Replacing attached file resource in question \'{}\''.format(
                    element['title']))
            replace_question_resource(element, index, resource_ids,
                                      fetched_resources, first_org, second_org)
        elif type == 'calculated' and 'LOOKUP' in element['calculate_expr']:
            replace_calculated_expression(element, fetched_resources,
                                          resource_ids, first_org, second_org,
                                          index)
        else:
            continue
    return elements


def main():
    logging.basicConfig()

    dm_one_args = {'org_id': 'ORG_ID_ONE',
                   'api_key': 'API_KEY_ONE'}

    dm_two_args = {'org_id': 'ORG_ID_TWO',
                   'api_key': 'API_KEY_TWO'}

    dm_one = DeviceMagic(dm_one_args)  # Account 1
    dm_two = DeviceMagic(dm_two_args)  # Account 2

    resources = dm_one.resource.all()['resources']  # Fetch all resources ids
    resource_ids = []
    for resource in resources:
        resource_ids.append(resource['id'])

    logging.info("Resource id's copied from organization...")

    form_ids = []  # Forms to copy
    fetched_resources = {}
    index = 0
    for id in form_ids:
        data = dm_one.form.details(id)  # Retrieve the form definition
        data['children'] = clone_replace_resources(data['children'],
                                                   resource_ids,
                                                   index,
                                                   fetched_resources,
                                                   dm_one,
                                                   dm_two)
        cloned_form = json.dumps(data)

        form = dm_two.form.create(cloned_form)  # Create form in Account 2
        print('Form created: {}'.format(form['name']))


if __name__ == "__main__":
    main()
