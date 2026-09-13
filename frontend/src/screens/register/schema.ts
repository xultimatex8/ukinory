import { z } from "zod";

const commonPasswords = [
  "password",
  "12345678",
  "123456789",
  "qwerty",
  "qwerty123",
  "1234567890",
  "password123",
  "admin",
  "letmein",
  "welcome",
];

export const registerSchema = z
  .object({
    username: z
      .string()
      .trim()
      .min(1, "Username is required.")
      .max(150, "Username must be 150 characters or fewer."),

    email: z
      .string()
      .trim()
      .min(1, "Email is required.")
      .email("Enter a valid email address."),

    password: z
      .string()
      .min(
        8,
        "This password is too short. It must contain at least 8 characters.",
      )
      .refine(
        (password) => !/^\d+$/.test(password),
        "This password is entirely numeric.",
      )
      .refine(
        (password) => !commonPasswords.includes(password.toLowerCase()),
        "This password is too common.",
      ),

    confirmPassword: z
      .string()
      .min(1, "Please confirm your password."),
  })
  .superRefine(({ password, confirmPassword }, context) => {
    if (password !== confirmPassword) {
      context.addIssue({
        code: "custom",
        path: ["confirmPassword"],
        message: "Passwords do not match.",
      });
    }
  });

export type RegisterData = z.infer<typeof registerSchema>;