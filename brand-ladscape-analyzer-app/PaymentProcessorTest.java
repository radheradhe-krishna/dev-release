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
        System.out.println();
        System.out.println("Verifying test results:");
        
        boolean allTestsPassed = true;
        
        if (!processor.isCurrencySupported("USD")) {
            System.out.println("✗ FAIL: USD should be supported");
            allTestsPassed = false;
        }
        if (!processor.isCurrencySupported("EUR")) {
            System.out.println("✗ FAIL: EUR should be supported");
            allTestsPassed = false;
        }
        if (!processor.isCurrencySupported("INR")) {
            System.out.println("✗ FAIL: INR should be supported");
            allTestsPassed = false;
        }
        if (processor.isCurrencySupported("GBP")) {
            System.out.println("✗ FAIL: GBP should not be supported");
            allTestsPassed = false;
        }
        if (!processor.safeCheck("USD")) {
            System.out.println("✗ FAIL: USD should pass safeCheck");
            allTestsPassed = false;
        }
        if (!processor.safeCheck("EUR")) {
            System.out.println("✗ FAIL: EUR should pass safeCheck");
            allTestsPassed = false;
        }
        if (!processor.safeCheck("INR")) {
            System.out.println("✗ FAIL: INR should pass safeCheck");
            allTestsPassed = false;
        }
        if (processor.safeCheck("GBP")) {
            System.out.println("✗ FAIL: GBP should not pass safeCheck");
            allTestsPassed = false;
        }
        
        System.out.println();
        if (allTestsPassed) {
            System.out.println("✓ All tests passed!");
        } else {
            System.out.println("✗ Some tests failed!");
            System.exit(1);
        }
    }
}
