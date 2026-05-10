# Storage Engines — Day 1/7

**Week:** 2026-19  
**Progress:** Day 1/7 · Storage Engines · depth-first  

---

## Today's Digest

### Day 1: Mental Model of Storage Engines

To effectively understand storage engines, we must first frame them within the broader context of database systems. At a high level, storage engines are the foundational components that manage how data is stored, retrieved, and manipulated on physical storage devices. However, the real insights come from examining the constraints and design choices that led to their development, as well as the trade-offs that come with those choices.

#### Constraints: The Underlying Realities

Every engineering decision is a response to a set of constraints. In the case of storage engines, these constraints can be categorized into three primary areas:

1. **Performance**: As datasets grow, so do the performance demands for reading and writing data. Different workloads (OLTP vs. OLAP) have vastly different performance characteristics. OLTP (Online Transaction Processing) systems require low-latency access to data for frequent transactions, while OLAP (Online Analytical Processing) systems often prioritize high-throughput access for querying large datasets.

2. **Durability and Consistency**: Data must be stored reliably and consistently. This is where the ACID properties (Atomicity, Consistency, Isolation, Durability) come into play. The design of a storage engine must ensure that it can handle crashes, concurrent access, and various failure scenarios without losing integrity.

3. **Scalability**: As applications grow, the ability to handle increased loads without significant degradation in performance is crucial. This could mean scaling vertically (adding more resources to a single machine) or horizontally (distributing data across multiple machines).

#### Design Choices: The Architecture of Storage

Given these constraints, storage engines make several critical design choices that shape their behavior and performance:

1. **Data Organization**: Storage engines choose how to organize data on disk. This could be in a row-oriented format, as seen in traditional relational databases, or a column-oriented format, favored by analytical systems. For instance, row stores are better for transactional workloads, while column stores optimize read-heavy analytical queries.

2. **Indexing Mechanism**: The choice of indexing structures (B-trees, LSM-trees, etc.) directly affects read and write performance. B-trees allow for efficient range queries but can become fragmented over time, impacting write efficiency. In contrast, LSM-trees optimize for write-heavy workloads by batching writes, at the cost of more complex read patterns.

3. **Data Durability Strategies**: Different storage engines adopt various strategies for ensuring data durability. Some may leverage write-ahead logging (WAL) to ensure that all changes are logged before they are applied to the main data store. Others may use checkpointing techniques to balance between performance and durability.

4. **Concurrency Control**: Mechanisms like locking and multi-version concurrency control (MVCC) dictate how the storage engine manages simultaneous transactions. The choice between these methods can lead to significant differences in performance and scalability under concurrent load.

5. **Compression and Compaction**: To manage disk space and improve I/O performance, many engines integrate data compression and compaction strategies. While compression can reduce the amount of data stored, it often introduces CPU overhead during read and write operations.

#### Trade-offs: The Cost of Choices

With each design choice comes a trade-off. Understanding these trade-offs is essential for making informed decisions about which storage engine to use in a particular context.

- **Row vs. Column Storage**: Choosing a row-oriented engine may offer faster writes for transactional workloads, but it can lead to inefficient reads for analytical queries. Conversely, columnar storage excels in read-heavy contexts but may struggle with transactional workloads.

- **B-tree vs. LSM-tree**: While LSM-trees provide better write performance, they can lead to increased read latencies due to the complexities of merging data from multiple locations. B-trees, while simpler, may incur higher write amplification.

- **Durability vs. Performance**: Engines that prioritize durability, such as those employing WAL, might sacrifice write performance during high-load scenarios. This trade-off can lead to bottlenecks if not managed correctly.

- **Concurrency Control**: Opting for MVCC can simplify transaction management and improve throughput at the cost of increased storage overhead due to maintaining multiple versions of data.

#### Core Tension Leading into Day 2

As we explore the internal mechanisms of storage engines over the coming days, a core tension will emerge: the intricate balance between performance, durability, and complexity. Each storage engine is essentially a compromise among these competing interests. Understanding the detailed trade-offs of various internal implementations—such as how LSM-trees efficiently handle writes through compaction strategies or how MVCC manages concurrency without locking—will be crucial in resolving this tension.

In Day 2, we will dissect these internal mechanisms, revealing how different storage engines navigate the constraints and design choices discussed today. By doing so, we will gain a deeper appreciation for the engineering decisions that shape the performance and reliability of storage systems in the wild.

---

## Curated Links

- **[SURFACE]** [Database engine (Wikipedia)](https://en.wikipedia.org/wiki/Database_engine)  
  *This article provides a foundational overview of what a database engine is and its role within database management systems, making it essential for understanding the broader context of storage engines.*
- **[DEEP]** [Writing a MySQL storage engine from scratch (2016)](https://www.codeproject.com/articles/1107279/writing-a-mysql-storage-engine-from-scratch)  
  *This article offers a detailed, hands-on approach to building a storage engine, providing insights into the practical challenges and considerations involved in storage engine development.*
- **[MID]** [MySQL Storage Engines - Part 1](https://www.youtube.com/watch?v=dxNT4_1qiA8)  
  *This video discusses various MySQL storage engines, including their specific use cases and functionalities, which is crucial for understanding different storage options available.*
- **[MID]** [Data storage engines: the 5 must-know components](https://www.youtube.com/watch?v=K4YMuDzbu_E)  
  *This video breaks down the essential components of storage engines, helping to clarify their roles and importance in the data management stack.*
- **[DEEP]** [A new storage engine for PostgreSQL to provide better control over bloat](http://amitkapila16.blogspot.com/2018/03/zheap-storage-engine-to-provide-better.html)  
  *This article presents an innovative approach to a storage engine designed to tackle specific issues such as data bloat in PostgreSQL, offering insights into ongoing developments in storage engine technology.*

---

## Reference Pick

**Designing Data-Intensive Applications — Martin Kleppmann**

This book is an exceptional starting point for understanding storage engines because it offers a comprehensive overview of the entire data stack with a focus on the fundamental principles that govern data storage and retrieval. In Chapter 3, Kleppmann introduces key concepts such as data models, query languages, and the trade-offs involved in different storage solutions, providing a solid mental model for where storage engines fit in the broader context of data systems. The accessible writing style and rich illustrations make complex topics digestible, while the insights into distributed systems and consistency models lay the groundwork for deeper exploration in subsequent days. This resource is perfect for establishing a foundational understanding, making it clearer why storage engines are crucial for building scalable and efficient data-intensive applications.

---

## Raw Research Context

```
# Research Bundle: Storage Engines
Day 1/7 | Focus: Mental model — where this fits in the stack and why it exists | Mode: depth_first

## [1] [SURFACE] Database engine
Source: Wikipedia | URL: https://en.wikipedia.org/wiki/Database_engine
A database engine is the underlying software component that a database management system (DBMS) uses to create, read, update and delete (CRUD) data from a database. Most database management systems include their own application programming interface (API) that allows the user to interact with their underlying engine without going through the user interface of the DBMS.

## [2] [MID] HSE: Heterogeneous-memory storage engine designed for SSDs
Source: HackerNews | URL: https://github.com/hse-project/hse


## [3] [MID] A new storage engine for PostgreSQL to provide better control over bloat
Source: HackerNews | URL: http://amitkapila16.blogspot.com/2018/03/zheap-storage-engine-to-provide-better.html


## [4] [MID] Writing a MySQL storage engine from scratch (2016)
Source: HackerNews | URL: https://www.codeproject.com/articles/1107279/writing-a-mysql-storage-engine-from-scratch


## [5] [SURFACE] MySQL Storage Engines - Part 1
Source: YouTube | URL: https://www.youtube.com/watch?v=dxNT4_1qiA8
MySQL Storage Engines, we are discussing about Innodb, MyIsam, Archive and Memory Engines.

## [6] [SURFACE] Data storage engines: the 5 must-know components
Source: YouTube | URL: https://www.youtube.com/watch?v=K4YMuDzbu_E
All databases have a "storage engine" subsystem. But even these are further divided into components that manage transactions, ...

## Curated References from Taxonomy
**Easy**: 'Designing Data-Intensive Applications' ch.3 — Kleppmann
**Mid**: deep-dive-databases (natenberenstein GitHub), LevelDB implementation notes — Jeff Dean
**Deep**: The Log-Structured Merge-Tree — O'Neil et al. (1996), Monkey: Optimal Navigable Key-Value Store — Dayan et al.
**Niche**: RocksDB wiki + Tuning Guide, WiscKey paper (FAST '16), Badger (dgraph) internals blog
```
