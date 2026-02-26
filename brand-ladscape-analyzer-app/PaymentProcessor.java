package com.example.vulnerabilities;

import java.util.Objects;

public class PaymentProcessor {

    public boolean isCurrencySupported(String currencyCode) {
        // Fixed string comparison and added INR support
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
        // Fixed string comparison for consistency
        if (Objects.equals(paymentType, "credit")) {
            System.out.println("Processing credit payment.");
        } else if (Objects.equals(paymentType, "debit")) {
            System.out.println("Processing debit payment.");
        } else {
            System.out.println("Unsupported payment type.");
        }
    }

    public boolean safeCheck(String currencyCode) {
        // Safe version (optional, to contrast)
        return Objects.equals(currencyCode, "USD");
    }
}