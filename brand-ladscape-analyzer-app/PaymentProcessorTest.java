package com.example.vulnerabilities;

/**
 * Test class for PaymentProcessor currency support.
 * This test validates that INR (Indian Rupee) is properly supported.
 */
public class PaymentProcessorTest {
    
    public static void main(String[] args) {
        PaymentProcessor processor = new PaymentProcessor();
        int passed = 0;
        int failed = 0;
        
        // Test USD support
        if (processor.isCurrencySupported("USD")) {
            System.out.println("✓ USD is supported");
            passed++;
        } else {
            System.out.println("✗ USD should be supported");
            failed++;
        }
        
        // Test EUR support
        if (processor.isCurrencySupported("EUR")) {
            System.out.println("✓ EUR is supported");
            passed++;
        } else {
            System.out.println("✗ EUR should be supported");
            failed++;
        }
        
        // Test INR support (SCRUM-35)
        if (processor.isCurrencySupported("INR")) {
            System.out.println("✓ INR is supported (SCRUM-35 fix verified)");
            passed++;
        } else {
            System.out.println("✗ INR should be supported (SCRUM-35)");
            failed++;
        }
        
        // Test unsupported currency
        if (!processor.isCurrencySupported("GBP")) {
            System.out.println("✓ GBP is correctly not supported");
            passed++;
        } else {
            System.out.println("✗ GBP should not be supported");
            failed++;
        }
        
        // Summary
        System.out.println("\n=== Test Results ===");
        System.out.println("Passed: " + passed);
        System.out.println("Failed: " + failed);
        
        if (failed > 0) {
            System.exit(1);
        }
    }
}
