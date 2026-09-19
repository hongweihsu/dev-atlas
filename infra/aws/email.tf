resource "aws_sesv2_email_identity" "app_domain" {
  email_identity = var.root_domain
}

resource "aws_route53_record" "ses_dkim" {
  count   = 3
  zone_id = data.aws_route53_zone.portfolio.zone_id
  name    = "${aws_sesv2_email_identity.app_domain.dkim_signing_attributes[0].tokens[count.index]}._domainkey.${var.root_domain}"
  type    = "CNAME"
  ttl     = 300
  records = ["${aws_sesv2_email_identity.app_domain.dkim_signing_attributes[0].tokens[count.index]}.dkim.amazonses.com"]
}
