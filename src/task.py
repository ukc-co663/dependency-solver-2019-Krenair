#!/usr/bin/python3
# By Alex Monk <am2121@kent.ac.uk> for CO633, 2019
import argparse
import json

argparser = argparse.ArgumentParser()
argparser.add_argument('repository', type=argparse.FileType('r'))
argparser.add_argument('state', type=argparse.FileType('r'))
argparser.add_argument('constraints', type=argparse.FileType('r'))
args = argparser.parse_args()

init_repo_desc = json.load(args.repository)

init_state = json.load(args.state)
init_state = list(map(lambda s: tuple(s.split('=')), init_state))

init_constraints = json.load(args.constraints)

def normalise_version(ver):
    return '.'.join(map(str, map(int, ver.split('.'))))

def split_namever(namever):
    if '<=' in namever:
        name, version = namever.split('<=')
        version = normalise_version(version)
        return name, lambda pv: normalise_version(pv) <= version
    elif '>=' in namever:
        name, version = namever.split('>=')
        version = normalise_version(version)
        return name, lambda pv: normalise_version(pv) >= version
    elif '<' in namever:
        name, version = namever.split('<')
        version = normalise_version(version)
        return name, lambda pv: normalise_version(pv) < version
    elif '>' in namever:
        name, version = namever.split('>')
        version = normalise_version(version)
        return name, lambda pv: normalise_version(pv) > version
    elif '=' in namever:
        name, version = namever.split('=')
        version = normalise_version(version)
        return name, lambda pv: normalise_version(pv) == version
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
                        return False
                break
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
            to_remove_from_state = list(find_packages_in_state(state, constraint[1:]))
            state = list(set(state) - set(to_remove_from_state))
            for subcommands, substate in get_states(repo_desc, state, constraints):
                yield ['-{}={}'.format(*p) for p in to_remove_from_state] + subcommands, substate
        elif constraint[0] == '+':
            if gen_has_item(find_packages_in_state(state, constraint[1:])):
                yield from get_states(repo_desc, state, constraints)
            else:
                for package in find_packages_in_repo(repo_desc, constraint[1:]):
                    new_package = package['name'], package['version']
                    cmd = '+{}={}'.format(*new_package)
                    assert new_package not in state
                    depends = package.get('depends', [])
                    conflicts = package.get('conflicts', [])
                    conflicts_constraints = list(map(lambda x: '-' + x, conflicts))
                    for extra_constraints in list(handle_dgs(depends)):
                        extra_constraints = list(map(lambda x: '+' + x, extra_constraints))
                        try:
                            for subcommands, substate in get_states(repo_desc, state, conflicts_constraints + extra_constraints + constraints):
                                if new_package not in substate:
                                    subcommands = subcommands + [cmd]
                                    substate = substate + [new_package]
                                yield subcommands, list(set(substate))
                        except RecursionError:
                            return [] # give up, hopefully another branch will handle it - this handles the seen-3 problem by killing the A -> B -> D -> A dependency loop and forcing only the A -> C one to be considered

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
