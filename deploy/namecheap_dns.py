#!/usr/bin/env python3
"""Safely list or upsert one Namecheap DNS host without dropping other records."""

from __future__ import annotations

import argparse
import os
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET


API_URL = "https://api.namecheap.com/xml.response"
NS = {"nc": "http://api.namecheap.com/xml.response"}


def required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"missing environment variable: {name}")
    return value


def api_call(command: str, **params: str) -> ET.Element:
    username = required_env("NAMECHEAP_USERNAME")
    query = {
        "ApiUser": username,
        "ApiKey": required_env("NAMECHEAP_API_KEY"),
        "UserName": username,
        "ClientIp": required_env("NAMECHEAP_CLIENT_IP"),
        "Command": command,
        **params,
    }
    url = f"{API_URL}?{urllib.parse.urlencode(query)}"
    with urllib.request.urlopen(url, timeout=30) as response:
        root = ET.fromstring(response.read())
    if root.attrib.get("Status") != "OK":
        errors = [node.text or "unknown error" for node in root.findall("nc:Errors/nc:Error", NS)]
        raise RuntimeError("; ".join(errors) or "Namecheap API request failed")
    return root


def get_hosts(sld: str, tld: str) -> list[dict[str, str]]:
    root = api_call("namecheap.domains.dns.getHosts", SLD=sld, TLD=tld)
    result = root.find(".//nc:DomainDNSGetHostsResult", NS)
    if result is None:
        raise RuntimeError("Namecheap response did not contain DNS hosts")
    hosts: list[dict[str, str]] = []
    for node in result.findall("nc:host", NS):
        hosts.append(
            {
                "Name": node.attrib["Name"],
                "Type": node.attrib["Type"],
                "Address": node.attrib["Address"],
                "MXPref": node.attrib.get("MXPref", "10"),
                "TTL": node.attrib.get("TTL", "300"),
            }
        )
    return hosts


def set_hosts(sld: str, tld: str, hosts: list[dict[str, str]]) -> None:
    params: dict[str, str] = {"SLD": sld, "TLD": tld}
    for index, host in enumerate(hosts, start=1):
        params[f"HostName{index}"] = host["Name"]
        params[f"RecordType{index}"] = host["Type"]
        params[f"Address{index}"] = host["Address"]
        params[f"MXPref{index}"] = host.get("MXPref", "10")
        params[f"TTL{index}"] = host.get("TTL", "300")
    root = api_call("namecheap.domains.dns.setHosts", **params)
    result = root.find(".//nc:DomainDNSSetHostsResult", NS)
    if result is None or result.attrib.get("IsSuccess", "false").lower() != "true":
        raise RuntimeError("Namecheap did not confirm DNS update")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sld", required=True)
    parser.add_argument("--tld", required=True)
    parser.add_argument("--host")
    parser.add_argument("--address")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    hosts = get_hosts(args.sld, args.tld)
    if not args.apply:
        for host in hosts:
            print(f"{host['Name']}\t{host['Type']}\t{host['Address']}\tTTL={host['TTL']}")
        return 0

    if not args.host or not args.address:
        parser.error("--apply requires --host and --address")
    updated = [host for host in hosts if host["Name"].lower() != args.host.lower()]
    updated.append(
        {"Name": args.host, "Type": "A", "Address": args.address, "MXPref": "10", "TTL": "300"}
    )
    set_hosts(args.sld, args.tld, updated)

    verified = [host for host in get_hosts(args.sld, args.tld) if host["Name"].lower() == args.host.lower()]
    if len(verified) != 1 or verified[0]["Type"] != "A" or verified[0]["Address"] != args.address:
        raise RuntimeError("DNS update could not be verified")
    print(f"updated {args.host}.{args.sld}.{args.tld} -> {args.address}; preserved {len(updated) - 1} records")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
