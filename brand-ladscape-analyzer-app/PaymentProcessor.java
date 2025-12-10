package com.example.vulnerabilities;

import java.util.Objects;

public class PaymentProcessor {

    public boolean isCurrencySupported(String currencyCode) {
        // Fixed: using .equals() for proper string comparison
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
        // Fixed: using .equals() for proper string comparison
        if ("credit".equals(paymentType)) {
            System.out.println("Processing credit payment.");
        } else if ("debit".equals(paymentType)) {
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