#!/usr/bin/env python3
from collections.abc import Callable
import copy
import hashlib
import json
import subprocess
import sys
import os

import nbtlib
import requests

def main():
	versions = fetch_versions()
	# for type in ('assets', 'assets-json', 'assets-tiny', 'data', 'data-json', 'summary', 'registries', 'diff', 'history'):
	# 	os.chdir(type)
	# 	subprocess.run(['git', 'add', '.'], capture_output=True)
	# 	subprocess.run(['git', 'reset', '--hard', f'1.14.3-pre1-{type}'], capture_output=True)
	# 	for version in versions[versions.index('1.14.3-pre2'):versions.index('1.14.3') + 1]:
	# 		subprocess.run(['git', 'tag', '-d', f'{version}-{type}'], capture_output=True)
	# 	os.chdir('..')
	for version in versions[versions.index('1.14'):versions.index('1.14.3-pre4') + 1]:
		for type in ['assets', 'data', 'registries', 'summary']:
			os.chdir(type)
			subprocess.run(['git', 'checkout', f'{version}-{type}'], capture_output=True)
			os.chdir('..')

		for file_name in (f"{dir}{os.sep}{file}" for dir, _, files in os.walk("history") if not any(True for seg in dir.split(os.sep) if seg.startswith('.'))  for file in files if not (file.endswith(".min.json") or file.endswith(".min.mcmeta") or file.endswith(".min.mchistory")) and (file.endswith(".json") or file.endswith(".mcmeta") or file.endswith(".mchistory") or file.endswith(".nbt"))):
			content = None
			src_file_name = file_name.removeprefix(f'history{os.sep}').removesuffix('.mchistory')
			src_content = None
			if file_name.endswith('.nbt'):
				file_content = nbtlib.load(file_name)
				content = build_version(versions, version, file_content, lambda d: nbtlib.Compound(d), lambda l: nbtlib.List(l))
				if os.path.isfile(src_file_name):
					src_content = nbtlib.load(src_file_name)
					del src_content.root["DataVersion"]
			else:
				with open(file_name, 'r', encoding='utf-8') as file:
					file_content = json.load(file)
					content = build_version(versions, version, file_content)
				if os.path.isfile(src_file_name):
					if file_name.endswith('.mchistory'):
						sha1 = hashlib.sha1()
						with open(src_file_name, "rb") as source:
							while chunk := source.read(8192):
								sha1.update(chunk)
						src_content = sha1.hexdigest()
					else:
						with open(src_file_name, 'r', encoding='utf-8') as file:
							src_content = json.load(file)
			if not is_equal(content, src_content):
				print(f'Unexpected content for {src_file_name} in {version}', file=sys.stderr)
			
	
	for type in ['assets', 'data', 'registries', 'summary']:
		os.chdir(type)
		subprocess.run(['git', 'checkout', type], capture_output=True)
		os.chdir('..')

def is_versioned_entry(val):
	return isinstance(val, list) and len(val) > 0 and isinstance(val[-1], dict) and '$$value' in val[-1]

def is_equal(a, b):
	if a == b: return True
	if isinstance(a, dict) and isinstance(b, dict):
		if (len(a) != len(b)): return False
		keys = set(a.keys()).union(b.keys())
		if (len(a) != len(keys)): return False
		for k in keys:
			if not is_equal(a[k], b[k]): return False
		return True
	if isinstance(a, list) and isinstance(b, list):
		if (len(a) != len(b)): return False
		for i in range(len(a)):
			if not is_equal(a[i], b[i]): return False
		return True
	return False

def build_version(versions: list[str], version: str, target, create_dict: Callable[[dict], dict] = lambda d: d, create_list: Callable[[list], list] = lambda l: l):
	if is_versioned_entry(target):
		version_index = versions.index(version)
		selected = None
		for current in target:
			current_version = current.get('$$version', '$$initial')
			if isinstance(current_version, list):
				current_version = current['$$version'][0] if len(current['$$version']) > 0 else '$$initial'
			
			if current_version == '$$initial' or versions.index(current_version) <= version_index:
				if isinstance(current.get('$$version'), list) and len(current['$$version']) == 2:
					if versions.index(current['$$version'][1]) <= version_index:
						selected = None
						continue
				selected = current['$$value']
		target = selected
	
	if isinstance(target, dict):
		if isinstance(target, nbtlib.File):
			target = copy.copy(target)
			target.root = build_version(versions, version, target.root, create_dict, create_list)
			return target

		new_target = {}
		for [k, v] in target.items():
			new_v = build_version(versions, version, v, create_dict, create_list)
			if new_v != None:
				new_target[k] = new_v

		return create_dict(new_target)
	
	if isinstance(target, list):
		new_target = []
		for val in target:
			val = build_version(versions, version, val, create_dict, create_list)
			if val != None:
				new_target.append(val)
		return create_list(new_target)
		
	return target

def fetch_versions() -> list[str]:
	# === fetch manifest ===
	manifest = requests.get('https://piston-meta.mojang.com/mc/game/version_manifest_v2.json').json()
	for v in manifest['versions']:
		v['id'] = v['id'].replace(' Pre-Release ', '-pre')
	version_ids = [v['id'] for v in manifest['versions']]

	# Fix version order anomaly around 1.16.5
	v1165 = version_ids.index('1.16.5')
	v20w51a = version_ids.index('20w51a')
	v1164 = version_ids.index('1.16.4')
	version_ids = [*version_ids[:v1165], *version_ids[v20w51a:v1164], *version_ids[v1165:v20w51a], *version_ids[v1164:]]
	version_ids.reverse()

	return version_ids

if __name__ == '__main__':
	main()