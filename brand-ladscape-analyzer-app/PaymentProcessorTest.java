package com.example.vulnerabilities;

public class PaymentProcessorTest {
    public static void main(String[] args) {
        PaymentProcessor processor = new PaymentProcessor();
        
        // Test isCurrencySupported with all currencies
        System.out.println("Testing isCurrencySupported:");
        System.out.println("USD supported: " + processor.isCurrencySupported("USD"));
        System.out.println("EUR supported: " + processor.isCurrencySupported("EUR"));
        System.out.println("INR supported: " + processor.isCurrencySupported("INR"));
        System.out.println("GBP supported: " + processor.isCurrencySupported("GBP"));
        
        System.out.println();
        
        // Test safeCheck with all currencies
        System.out.println("Testing safeCheck:");
        System.out.println("USD safe: " + processor.safeCheck("USD"));
        System.out.println("EUR safe: " + processor.safeCheck("EUR"));
        System.out.println("INR safe: " + processor.safeCheck("INR"));
        System.out.println("GBP safe: " + processor.safeCheck("GBP"));
        
        System.out.println();
        
        // Test processPayment
        System.out.println("Testing processPayment:");
        processor.processPayment("credit");
        processor.processPayment("debit");
        processor.processPayment("cash");
        
        // Verify all tests passed
        boolean allTestsPassed = 
            processor.isCurrencySupported("USD") &&
            processor.isCurrencySupported("EUR") &&
            processor.isCurrencySupported("INR") &&
            !processor.isCurrencySupported("GBP") &&
            processor.safeCheck("USD") &&
            processor.safeCheck("EUR") &&
            processor.safeCheck("INR") &&
            !processor.safeCheck("GBP");
        
        System.out.println();
        if (allTestsPassed) {
            System.out.println("✓ All tests passed!");
        } else {
            System.out.println("✗ Some tests failed!");
            System.exit(1);
        }
    }
}
