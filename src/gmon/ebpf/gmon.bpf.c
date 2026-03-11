#include <linux/bpf.h>
#include <linux/if_ether.h>
#include <linux/ip.h>
#include <linux/tcp.h>
#include <linux/udp.h>
#include <linux/in.h>
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_endian.h>

#define MAX_ENTRIES 10240
#define MAX_DOMAIN_LEN 64

// Key: (SrcIP, DstIP, DstPort, Proto)
struct flow_key {
    __u32 saddr;
    __u32 daddr;
    __u16 dport;
    __u8  proto;
};

// Value: (bytes, pkts, last_seen)
struct flow_stats {
    __u64 bytes;
    __u64 pkts;
    __u64 last_seen;
};

// Maps for traffic stats
struct {
    __uint(type, BPF_MAP_TYPE_HASH);
    __uint(max_entries, MAX_ENTRIES);
    __type(key, struct flow_key);
    __type(value, struct flow_stats);
} active_flows SEC(".maps");

// Map for Domain names (IP -> Domain)
struct {
    __uint(type, BPF_MAP_TYPE_HASH);
    __uint(max_entries, MAX_ENTRIES);
    __type(key, __u32); // IP address
    __type(value, char[MAX_DOMAIN_LEN]);
} dns_cache SEC(".maps");

// Map for SNI ( (IP, Port) -> Domain )
struct sni_key {
    __u32 ip;
    __u16 port;
};
struct {
    __uint(type, BPF_MAP_TYPE_HASH);
    __uint(max_entries, MAX_ENTRIES);
    __type(key, struct sni_key);
    __type(value, char[MAX_DOMAIN_LEN]);
} sni_cache SEC(".maps");

// Map for restricted domains (Key: Domain, Value: Action)
struct {
    __uint(type, BPF_MAP_TYPE_HASH);
    __uint(max_entries, 1024);
    __type(key, char[MAX_DOMAIN_LEN]);
    __type(value, __u8); // 1 = Block, 0 = Allow
} blocked_domains SEC(".maps");

SEC("tc")
int gmon_tc_main(struct __sk_buff *skb) {
    void *data_end = (void *)(long)skb->data_end;
    void *data = (void *)(long)skb->data;

    struct ethhdr *eth = data;
    if ((void *)(eth + 1) > data_end) return TC_ACT_OK;

    if (bpf_ntohs(eth->h_proto) != ETH_P_IP) return TC_ACT_OK;

    struct iphdr *ip = data + sizeof(struct ethhdr);
    if ((void *)(ip + 1) > data_end) return TC_ACT_OK;

    struct flow_key key = {
        .saddr = ip->saddr,
        .daddr = ip->daddr,
        .proto = ip->protocol,
    };

    __u16 dport = 0;
    __u32 payload_off = sizeof(struct ethhdr) + (ip->ihl * 4);

    if (ip->protocol == IPPROTO_TCP) {
        struct tcphdr *tcp = data + payload_off;
        if ((void *)(tcp + 1) > data_end) return TC_ACT_OK;
        dport = bpf_ntohs(tcp->dest);
        key.dport = dport;
        
        // --- SNI Detection (Skeleton) ---
        __u8 *tls_payload = (void *)tcp + (tcp->doff * 4);
        if ((void *)(tls_payload + 5) <= data_end) {
            if (tls_payload[0] == 0x16 && tls_payload[1] == 0x03 && tls_payload[5] == 0x01) {
                 // In a full implementation, SNI parsing would happen here.
            }
        }
    } else if (ip->protocol == IPPROTO_UDP) {
        struct udphdr *udp = data + payload_off;
        if ((void *)(udp + 1) > data_end) return TC_ACT_OK;
        dport = bpf_ntohs(udp->dest);
        key.dport = dport;

        // --- DNS Detection (Skeleton) ---
        if (dport == 53 || bpf_ntohs(udp->source) == 53) {
            // In a full implementation, DNS parsing would happen here.
        }
    } else {
        return TC_ACT_OK;
    }

    // Update traffic stats
    struct flow_stats *stats = bpf_map_lookup_elem(&active_flows, &key);
    if (stats) {
        __sync_fetch_and_add(&stats->bytes, skb->len);
        __sync_fetch_and_add(&stats->pkts, 1);
        stats->last_seen = bpf_ktime_get_ns();
    } else {
        struct flow_stats new_stats = {
            .bytes = skb->len,
            .pkts = 1,
            .last_seen = bpf_ktime_get_ns(),
        };
        bpf_map_update_elem(&active_flows, &key, &new_stats, BPF_ANY);
    }

    return TC_ACT_OK;
}

char _license[] SEC("license") = "GPL";
