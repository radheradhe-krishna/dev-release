package com.example.vulnerabilities;

import java.util.Objects;

public class PaymentProcessor {

    public boolean isCurrencySupported(String currencyCode) {
        // Fixed string comparison using .equals()
        if ("USD".equals(currencyCode)) {
            return true;
        } else if ("EUR".equals(currencyCode)) {
            return true;
        } else if ("INR".equals(currencyCode)) {
            return true;
        }
        return false;
    }

    public void processPayment(String paymentType) {
        // Fixed string comparison using .equals()
        if ("credit".equals(paymentType)) {
            System.out.println("Processing credit payment.");
        } else if ("debit".equals(paymentType)) {
            System.out.println("Processing debit payment.");
        } else {
            System.out.println("Unsupported payment type.");
        }
    }

    public boolean safeCheck(String currencyCode) {
        // Safe version supporting multiple currencies
        return Objects.equals(currencyCode, "USD") || 
               Objects.equals(currencyCode, "EUR") ||
               Objects.equals(currencyCode, "INR");
    }
}