#!/usr/bin/python3
# Author: Alex Monk <am2121@kent.ac.uk>
# For CO633
# Solve seen tests:
# seen 0: all output states look OK - +1 mark if I can choose one
# TODO: seen 1: this kills the computer - 0 marks
# TODO: seen 2: no states output, but all tests should have solutions - 0 marks
# TODO: seen 3: produces one good result result but not the other, A and D... probably because A has not been installed by the time it considers D? loop? - 0 marks
# TODO: seen 4: traceback as = state stuff gets into tuple list state format - 0 marks
# TODO: seen 5: traceback as = state stuff gets into tuple list state format - 0 marks
# TODO: seen 6: outputs contain a bunch of duplicates packages in each state, last output state does not satisfy all constraints, remaining constraints are duplicates, possibly missing valid states - 0 marks
# TODO: seen 7: no states output, but all tests should have solutions - 0 marks
# TODO: seen 8: no states output, but all tests should have solutions - 0 marks
# TODO: seen 9: traceback as = state stuff gets into tuple list state format - 0 marks

# TODO: Docker
# TODO: output state in the original format
# TODO: keep track of installations/removals in each call
# TODO: assign cost to each potential solution and use it to return best result
import copy
import json
import sys

with open(sys.argv[1]) as f:
    init_repo_desc = json.load(f)

with open(sys.argv[2]) as f:
    init_state = json.load(f) # TODO: convert into our internal format to handle tests 4, 5 and 9

with open(sys.argv[3]) as f:
    init_constraints = json.load(f)

#print('Initial repository:', init_repo_desc)
#print('Initial state:', init_state)
#print('Initial constraints:', init_constraints)

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
    elif '=' in namever:
        name, version = namever.split('=')
        return name, lambda pv: pv == version
    else:
        return namever, lambda _: True

def is_state_valid(repo_desc, state):
    # not having any conflicts, all dependencies being satisfied
    #print('considering state', state)
    #print(state)
    for package, version in state:
        for repo_package in repo_desc:
            if package == repo_package['name'] and version == repo_package['version']:
                for conflict_namever in repo_package.get('conflicts', []):
                    name, version_match_f = split_namever(conflict_namever)
                    for installed_name, installed_version in state:
                        if installed_name == name and version_match_f(installed_version):
                            return False
                for dependency_group in repo_package.get('depends', []):
                    dg_satisfied = False
                    for dependency_namever in dependency_group:
                        # one of these dependencies in each dependency group must be present
                        name, version_match_f = split_namever(dependency_namever)
                        for installed_name, installed_version in state:
                            if installed_name == name and version_match_f(installed_version):
                                dg_satisfied = True
                                break
                        if dg_satisfied:
                            break
                    if not dg_satisfied:
                        #print('Dependency missing', repo_package, dependency_group, state)
                        return False
                break
        else:
            assert False # package name+version combo does not exist (!)
    return True

def get_states(repo_desc, state, constraints):
    if len(constraints) == 0:
        yield state
    else:
        constraint = constraints.pop()
        if constraint[0] == '-':
            #print('absent', constraint[1:])
            to_remove_from_state = []
            namever = constraint[1:]
            name, version_match_f = split_namever(namever)
            for installed_package in state:
                installed_package_name, installed_package_version = installed_package
                if installed_package_name == name and version_match_f(installed_package_version):
                    to_remove_from_state.append(installed_package)
            for package_to_remove in to_remove_from_state:
                state.remove(package_to_remove)
            yield from get_states(repo_desc, state, constraints)
        elif constraint[0] == '+':
            #print('present', constraint[1:])
            namever = constraint[1:]
            name, version_match_f = split_namever(namever)
            for package in repo_desc:
                if package['name'] == name and version_match_f(package['version']):
                    possible_states = [state + [(package['name'], package['version'])]]
                    for dependency_group in package.get('depends', []):
                        new_possible_states = []
                        for dependency_namever in dependency_group:
                            dependency_name, dependency_version_match_f = split_namever(dependency_namever)
                            for potential_dependency_package in repo_desc:
                                if potential_dependency_package['name'] == dependency_name and dependency_version_match_f(potential_dependency_package['version']):
                                    for possible_state in possible_states:
                                        extra_state = potential_dependency_package['name'], potential_dependency_package['version']
                                        # TODO: add in constraints for dependencies?
                                        new_possible_states += list(get_states(repo_desc, possible_state + [extra_state], constraints))
                        possible_states = new_possible_states
                    for possible_state in possible_states:
                        for substate in get_states(repo_desc, possible_state, constraints):
                            new_package = name, package['version']
                            if new_package not in substate:
                                substate.append(new_package)
                            yield substate
        else:
            assert False # nonexistent constraint type

for state in get_states(init_repo_desc, init_state, init_constraints):
    if is_state_valid(init_repo_desc, state):
        print(['+{}={}'.format(p, v) for (p, v) in state])
