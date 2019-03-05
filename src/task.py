#!/usr/bin/python3
# Author: Alex Monk <am2121@kent.ac.uk>
# For CO633
# Solve seen tests:
# seen 0: all output states look OK - +2 marks
# TODO: seen 1: this kills the computer - 0 marks
# TODO: seen 2: no states output, but all tests should have solutions - 0 marks
# seen 3: produces one good result result but not the other, A,B,D... probably because A has not been installed by the time it considers D? loop? - +2 marks
# TODO: seen 4: no states output, but all tests should have solutions - 0 marks
# seen 5: looks good, but could remove initial state B=3 and get lots more pairs such as B=2,A=3 and B=1,A=2 and B=1,A=3 - +2 marks
# TODO: seen 6: outputs contain a bunch of duplicates packages in each state, last output state does not satisfy all constraints, remaining constraints are duplicates, possibly missing valid states - 0 marks
# TODO: seen 7: no states output, but all tests should have solutions - 0 marks
# TODO: seen 8: no states output, but all tests should have solutions - 0 marks
# seen 9: might work - +2 marks
# TODO: output each state/commands in the right order?
import json
import sys

with open(sys.argv[1]) as f:
    init_repo_desc = json.load(f)

with open(sys.argv[2]) as f:
    init_state = json.load(f)

init_state = list(map(lambda s: tuple(s.split('=')), init_state))

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

def find_package_in_repo(repo_desc, namever):
    name, ver_match_f = split_namever(namever)
    return filter(lambda p: p['name'] == name and ver_match_f(p['version']), repo_desc)

def find_package_in_state(state, namever):
    name, ver_match_f = split_namever(namever)
    return filter(lambda p: p[0] == name and ver_match_f(p[1]), state)

def is_state_valid(repo_desc, state):
    # not having any conflicts, all dependencies being satisfied
    #print('considering state', state)
    #print(state)
    for package, version in state:
        for repo_package in repo_desc:
            if package == repo_package['name'] and version == repo_package['version']:
                for conflict_namever in repo_package.get('conflicts', []):
                    if len(list(find_package_in_state(state, conflict_namever))):
                        return False
                for dependency_group in repo_package.get('depends', []):
                    dg_satisfied = False
                    for dependency_namever in dependency_group:
                        # one of these dependencies in each dependency group must be present
                        if len(list(find_package_in_state(state, dependency_namever))):
                            dg_satisfied = True
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
        yield [], state
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
            for subcommands, substate in get_states(repo_desc, state, constraints):
                yield ['-{}={}'.format(*p) for p in to_remove_from_state] + subcommands, substate
        elif constraint[0] == '+':
            #print('present', constraint[1:])
            namever = constraint[1:]
            for package in find_package_in_repo(repo_desc, namever):
                new_package = package['name'], package['version']
                possible_states = [(['+{}={}'.format(*new_package)], state + [new_package])]
                for dependency_group in package.get('depends', []):
                    new_possible_states = []
                    for dependency_namever in dependency_group:
                        dependency_name, dependency_version_match_f = split_namever(dependency_namever)
                        for potential_dependency_package in find_package_in_repo(repo_desc, dependency_namever):
                            for possible_commands, possible_state in possible_states:
                                extra_state = potential_dependency_package['name'], potential_dependency_package['version']
                                # TODO: add in constraints for dependencies?
                                for subcommands, substate in get_states(repo_desc, possible_state + [extra_state], constraints):
                                    new_possible_states.append((['+{}={}'.format(*extra_state)] + possible_commands + subcommands, substate))
                    possible_states = new_possible_states
                for possible_commands, possible_state in possible_states:
                    for subcommands, substate in get_states(repo_desc, possible_state, constraints):
                        if new_package not in substate:
                            substate.append(new_package)
                            subcommands.append('+{}={}'.format(*new_package))
                        yield possible_commands + subcommands, substate
        else:
            assert False # nonexistent constraint type

package_costs = {}
for package in init_repo_desc:
    package_costs[package['name'], package['version']] = package['size']

commands_out = []
for commands, state in get_states(init_repo_desc, init_state, init_constraints):
    if is_state_valid(init_repo_desc, state):
        cost = sum(package_costs[tuple(map(lambda s: s.strip(), c[1:].split('=')))] for c in commands if c[0] == '+') + sum(10**6 for c in commands if c[0] == '-')
        commands_out.append((commands, cost))

(final_commands, final_cost), *_ = sorted(commands_out, key=lambda t: t[1])
print(json.dumps(final_commands))
