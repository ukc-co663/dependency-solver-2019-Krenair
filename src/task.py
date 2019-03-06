#!/usr/bin/python3
# Author: Alex Monk <am2121@kent.ac.uk>
# For CO633
# Solve seen tests:
# seen 0 - +2 marks
# TODO: seen 1: this kills the computer - 0 marks
# TODO: seen 2: no states output, but all tests should have solutions - 0 marks
# seen 3: originally produced one good result result but not the other, A,B,D... probably because A has not been installed by the time it considers D? loop? - +2 marks
# TODO: seen 4: no states output, but all tests should have solutions - 0 marks
# seen 5: looks good, but could remove initial state B=3 and get lots more pairs such as B=2,A=3 and B=1,A=2 and B=1,A=3 - +2 marks
# TODO: seen 6: used to output a bunch of duplicates packages in each state, last output state did not satisfy all constraints, remaining constraints were duplicates, possibly missing valid states. now no results - 0 marks
# seen 7 - +2 marks
# TODO: seen 8: no states output, but all tests should have solutions - 0 marks
# seen 9 - +2 marks
import argparse
import copy
import json

argparser = argparse.ArgumentParser()
argparser.add_argument('repository', type=argparse.FileType('r'))
argparser.add_argument('state', type=argparse.FileType('r'))
argparser.add_argument('constraints', type=argparse.FileType('r'))
argparser.add_argument('--debug', action='store_true')
args = argparser.parse_args()

init_repo_desc = json.load(args.repository)

init_state = json.load(args.state)
init_state = list(map(lambda s: tuple(s.split('=')), init_state))

init_constraints = json.load(args.constraints)

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

def find_packages_in_repo(repo_desc, namever):
    name, ver_match_f = split_namever(namever)
    return filter(lambda p: p['name'] == name and ver_match_f(p['version']), repo_desc)

def find_packages_in_state(state, namever):
    name, ver_match_f = split_namever(namever)
    return filter(lambda p: p[0] == name and ver_match_f(p[1]), state)

def gen_has_item(g):
    sentinel = object()
    return next(g, sentinel) is not sentinel

def is_state_valid(repo_desc, state):
    # not having any conflicts, all dependencies being satisfied
    #print('considering state', state)
    #print(state)
    for package, version in state:
        for repo_package in repo_desc:
            if package == repo_package['name'] and version == repo_package['version']:
                for conflict_namever in repo_package.get('conflicts', []):
                    if gen_has_item(find_packages_in_state(state, conflict_namever)):
                        return False
                for dependency_group in repo_package.get('depends', []):
                    dg_satisfied = False
                    for dependency_namever in dependency_group:
                        # one of these dependencies in each dependency group must be present
                        if gen_has_item(find_packages_in_state(state, dependency_namever)):
                            dg_satisfied = True
                            break
                    if not dg_satisfied:
                        #print('Dependency missing', repo_package, dependency_group, state)
                        return False
                break
        else:
            assert False # package name+version combo does not exist (!)
    return True

def handle_dgs(dgs, parents=[]):
    if len(dgs) == 0:
        yield parents
    else:
        dg, *more_dgs = dgs
        for d in dg:
            yield from handle_dgs(more_dgs, parents + [d])

def get_states(repo_desc, state, constraints):
    if len(constraints) == 0:
        yield [], state
    else:
        constraint = constraints.pop()
        if constraint[0] == '-':
            #print('absent', constraint[1:])
            to_remove_from_state = list(find_packages_in_state(state, constraint[1:]))
            for package_to_remove in to_remove_from_state:
                state.remove(package_to_remove)
            for subcommands, substate in get_states(repo_desc, copy.deepcopy(state), constraints):
                yield ['-{}={}'.format(*p) for p in to_remove_from_state] + subcommands, substate
        elif constraint[0] == '+':
            if gen_has_item(find_packages_in_state(state, constraint[1:])):
                yield from get_states(repo_desc, copy.deepcopy(state), constraints)
            else:
                #print('present', constraint[1:])
                for package in find_packages_in_repo(repo_desc, constraint[1:]):
                    new_package = package['name'], package['version']
                    cmd = '+{}={}'.format(*new_package)
                    assert new_package not in state
                    depends = package.get('depends', [])
                    conflicts = package.get('conflicts', [])
                    if args.debug:
                        print('considering', new_package)
                        print('depends', depends)
                        if len(conflicts):
                            print('TODO: will need to account for conflicts', conflicts) # TODO
                    for extra_constraints in list(handle_dgs(depends)):
                        extra_constraints = list(map(lambda x: '+' + x, extra_constraints))
                        if args.debug:
                            print('extra_constraints', extra_constraints)
                            print('all constraints', extra_constraints + constraints)
                            print('looking for subdependencies with state', state)
                        for subcommands, substate in get_states(repo_desc, copy.deepcopy(state), extra_constraints + constraints):
                            if cmd not in subcommands:
                                subcommands.append(cmd)
                                substate.append(new_package)
                            yield subcommands, list(set(substate))
                    if args.debug:
                        print('-----')
        else:
            assert False # nonexistent constraint type

package_costs = {}
for package in init_repo_desc:
    package_costs[package['name'], package['version']] = package['size']

commands_out = []
for commands, state in get_states(init_repo_desc, copy.deepcopy(init_state), init_constraints):
    if args.debug:
        print('potential commands', commands)
        print('potential state', state)
    if is_state_valid(init_repo_desc, state):
        cost = sum(package_costs[tuple(map(lambda s: s.strip(), c[1:].split('=')))] for c in commands if c[0] == '+') + sum(10**6 for c in commands if c[0] == '-')
        if args.debug:
            print('commands', commands)
            print('state', state)
        commands_out.append((commands, cost))
    elif args.debug:
        print('invalid!')
    if args.debug:
        print('---')

(final_commands, final_cost), *_ = sorted(commands_out, key=lambda t: t[1])
print(json.dumps(final_commands))

if args.debug:
    print('cost', final_cost)
