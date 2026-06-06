package com.example.rag;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableAsync;

/**
 * Enterprise Knowledge Base RAG Q&A System
 *
 * @author knowledge-rag-team
 */
@EnableAsync
@SpringBootApplication
public class KnowledgeRagApplication {

    public static void main(String[] args) {
        SpringApplication.run(KnowledgeRagApplication.class, args);
    }
}
