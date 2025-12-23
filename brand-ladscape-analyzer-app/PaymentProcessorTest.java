package com.example.vulnerabilities;

public class PaymentProcessorTest {
    
    public static void main(String[] args) {
        PaymentProcessor processor = new PaymentProcessor();
        
        // Test USD support
        System.out.println("Testing USD support: " + processor.isCurrencySupported("USD"));
        System.out.println("Testing USD with safeCheck: " + processor.safeCheck("USD"));
        
        // Test EUR support
        System.out.println("Testing EUR support: " + processor.isCurrencySupported("EUR"));
        System.out.println("Testing EUR with safeCheck: " + processor.safeCheck("EUR"));
        
        // Test INR support (newly added)
        System.out.println("Testing INR support: " + processor.isCurrencySupported("INR"));
        System.out.println("Testing INR with safeCheck: " + processor.safeCheck("INR"));
        
        // Test unsupported currency
        System.out.println("Testing GBP support (should be false): " + processor.isCurrencySupported("GBP"));
        System.out.println("Testing GBP with safeCheck (should be false): " + processor.safeCheck("GBP"));
        
        // All tests passed
        System.out.println("\nAll tests completed successfully!");
    }
}
