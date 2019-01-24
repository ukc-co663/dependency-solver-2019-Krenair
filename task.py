#!/usr/bin/python3
# TODO: make state be a list of strings with package name equals version
import json
import copy
with open('repository.json') as f:
    init_repo_desc = json.load(f)

with open('initial.json') as f:
    init_state = json.load(f)

with open('constraints.json') as f:
    init_constraints = json.load(f)

print('Initial repository:', init_repo_desc)
print('Initial state:', init_state)
print('Initial constraints:', init_constraints)

def split_namever(namever):
    if '<=' in namever:
        name, version = namever.split('<=')
        return name, lambda pv: pv <= version
    elif '>=' in namever:
        name, version = namever.split('>=')
        return name, lambda pv: pv >= version
    elif '<' in namever:
        name, version = namever.split('<')
        return name, lambda pv: pv < version
    elif '>' in namever:
        name, version = namever.split('>')
        return name, lambda pv: pv > version
    else:
        return namever, lambda _: True

def get_valid_states(repo_desc, state, constraints):
    if len(constraints) == 0:
        # return state only if it is valid, e.g. not having any conflicts, all dependencies being satisfied
        print('no constraints left, considering state', state)
        valid = True
        for package, version in state:
            for repo_package in repo_desc:
                if package == repo_package['name'] and version == repo_package['version']:
                    for conflict_namever in repo_package.get('conflicts', []):
                        name, version_match_f = split_namever(conflict_namever)
                        for conflict_package in repo_desc:
                            if conflict_package['name'] == name and version_match_f(conflict_package['version']):
                                return
                    for dependency_group in repo_package.get('depends', []):
                        dg_satisfied = False
                        for dependency_namever in dependency_group:
                            # one of these dependencies in each dependency group must be present
                            name, version_match_f = split_namever(dependency_namever)
                            for depend_package in repo_desc:
                                if depend_package['name'] == name and version_match_f(depend_package['version']):
                                    dg_satisfied = True
                                    break
                            if dg_satisfied:
                                break
                        if not dg_satisfied:
                            return
                    break
            else:
                assert False # package name+version combo does not exist (!)
        if valid:
            yield state
    else:
        constraint = constraints.pop()
        if constraint['type'] == 'absent':
            print('absent', constraint['names'])
            to_remove_from_state = []
            for namever in constraint['names']:
                name, version_match_f = split_namever(namever)
                for installed_package in state:
                    installed_package_name, installed_package_version = installed_package
                    if installed_package_name == name and version_match_f(installed_package_version):
                        to_remove_from_state.append(installed_package)
            for package_to_remove in to_remove_from_state:
                state.remove(package_to_remove)
            yield from get_valid_states(repo_desc, state, constraints)
        elif constraint['type'] == 'present':
            print('present', constraint['names'])
            for namever in constraint['names']:
                name, version_match_f = split_namever(namever)
                for package in repo_desc:
                    if package['name'] == name and version_match_f(package['version']):
                        constraints += map(lambda dg: {'type': 'present', 'names': dg}, package.get('depends', []))
                        for substate in get_valid_states(repo_desc, state, constraints):
                            yield substate + [(name, package['version'])]
        else:
            assert False # nonexistent constraint type

for state in get_valid_states(init_repo_desc, init_state, init_constraints):
    print('end state', state)

# TODO: what about multiple versions of the same package?
