package com.example.vulnerabilities;

import java.util.Objects;

public class PaymentProcessor {

    public boolean isCurrencySupported(String currencyCode) {
        // Fixed: Using proper string comparison with Objects.equals
        if (Objects.equals(currencyCode, "USD")) {
            return true;
        } else if (Objects.equals(currencyCode, "EUR")) {
            return true;
        } else if (Objects.equals(currencyCode, "INR")) {
            return true;
        }
        return false;
    }

    public void processPayment(String paymentType) {
        // Fixed: Using proper string comparison with Objects.equals
        if (Objects.equals(paymentType, "credit")) {
            System.out.println("Processing credit payment.");
        } else if (Objects.equals(paymentType, "debit")) {
            System.out.println("Processing debit payment.");
        } else {
            System.out.println("Unsupported payment type.");
        }
    }

    public boolean safeCheck(String currencyCode) {
        // Safe version - supports USD, EUR, and INR
        return Objects.equals(currencyCode, "USD") || 
               Objects.equals(currencyCode, "EUR") || 
               Objects.equals(currencyCode, "INR");
    }
}