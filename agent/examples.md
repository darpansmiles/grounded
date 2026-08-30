# Governed questions

1. “What was revenue last month by product category?” — returns the governed
   revenue table, verification status, and Contract-B lineage citation.
2. “Show the customer directory and emails.” — returns the customer directory;
   email is masked for the default viewer role.
3. “Describe the revenue metric.” — returns its measure, dimensions, policies,
   verification rules, and lineage citation.
4. “What was revenue last month by product category for an analyst with PII
   access?” — returns the same aggregate and demonstrates that role plumbing
   does not change a non-PII aggregate.
5. “What is GMV?” — refuses gracefully and lists the governed metrics that are
   currently available.
