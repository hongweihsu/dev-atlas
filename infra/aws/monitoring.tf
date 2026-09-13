resource "aws_sns_topic" "operations" {
  name = "${local.name}-operations"
  tags = local.common_tags
}

resource "aws_sns_topic_subscription" "operations_email" {
  topic_arn = aws_sns_topic.operations.arn
  protocol  = "email"
  endpoint  = var.budget_alert_email
}

resource "aws_cloudwatch_metric_alarm" "instance_status" {
  alarm_name          = "${local.name}-instance-status-check"
  alarm_description   = "DevAtlas EC2 failed its instance status check for ten minutes."
  namespace           = "AWS/EC2"
  metric_name         = "StatusCheckFailed_Instance"
  statistic           = "Maximum"
  period              = 300
  evaluation_periods  = 2
  comparison_operator = "GreaterThanOrEqualToThreshold"
  threshold           = 1
  treat_missing_data  = "missing"
  dimensions          = { InstanceId = aws_instance.app.id }
  alarm_actions       = [aws_sns_topic.operations.arn]
  ok_actions          = [aws_sns_topic.operations.arn]
  tags                = local.common_tags
}
