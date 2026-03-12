#ifndef KBUILD_MODNAME
#define KBUILD_MODNAME "gmon"
#endif

#include <linux/types.h>
#include <linux/pkt_cls.h>
#include <bcc/proto.h>

#define MAX_ENTRIES 10240
#define MAX_DOMAIN_LEN 64

// Key: (SrcIP, DstIP, DstPort, Proto)
struct flow_key {
    u32 saddr;
    u32 daddr;
    u16 dport;
    u8  proto;
};

// Value: (bytes, pkts, last_seen)
struct flow_stats {
    u64 bytes;
    u64 pkts;
    u64 last_seen;
};

// Wrapper for domain strings to avoid array syntax in BPF_HASH
struct domain_name {
    char name[MAX_DOMAIN_LEN];
};

// Maps for traffic stats
BPF_HASH(active_flows, struct flow_key, struct flow_stats, MAX_ENTRIES);

// Map for Domain names (IP -> Domain)
BPF_HASH(dns_cache, u32, struct domain_name, MAX_ENTRIES);

// Map for SNI ( (IP, Port) -> Domain )
struct sni_key {
    u32 ip;
    u16 dport;
};
BPF_HASH(sni_cache, struct sni_key, struct domain_name, MAX_ENTRIES);

// Map for restricted domains (Key: Domain, Value: Action)
BPF_HASH(blocked_domains, struct domain_name, u8, 1024);

int gmon_tc_main(struct __sk_buff *skb) {
    u8 *cursor = 0;

    // Check if it is an IPv4 packet
    struct ethernet_t *eth = cursor_advance(cursor, sizeof(*eth));
    if (eth->type != 0x0800) return TC_ACT_OK;

    struct ip_t *ip = cursor_advance(cursor, sizeof(*ip));
    
    struct flow_key key = {
        .saddr = ip->src,
        .daddr = ip->dst,
        .proto = ip->nextp,
    };

    if (ip->nextp == 6) { // TCP
        struct tcp_t *tcp = cursor_advance(cursor, sizeof(*tcp));
        key.dport = tcp->dst_port; // In BCC's proto.h, tcp_t has dst_port
    } else if (ip->nextp == 17) { // UDP
        struct udp_t *udp = cursor_advance(cursor, sizeof(*udp));
        key.dport = udp->dport;    // In BCC's proto.h, udp_t has dport
    } else {
        return TC_ACT_OK;
    }

    // Update traffic stats
    struct flow_stats *stats = active_flows.lookup(&key);
    if (stats) {
        lock_xadd(&stats->bytes, skb->len);
        lock_xadd(&stats->pkts, 1);
        stats->last_seen = bpf_ktime_get_ns();
    } else {
        struct flow_stats new_stats = {
            .bytes = skb->len,
            .pkts = 1,
            .last_seen = bpf_ktime_get_ns(),
        };
        active_flows.update(&key, &new_stats);
    }

    return TC_ACT_OK;
}
