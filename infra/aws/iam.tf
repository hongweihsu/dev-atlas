data "aws_iam_policy_document" "ec2_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "app" {
  name               = "${local.name}-ec2-role"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume_role.json
}

resource "aws_iam_role_policy_attachment" "ssm" {
  role       = aws_iam_role.app.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

data "aws_iam_policy_document" "runtime" {
  statement {
    sid = "ReadRuntimeParameters"
    actions = [
      "ssm:GetParameter",
      "ssm:GetParameters",
      "ssm:GetParametersByPath",
    ]
    resources = [
      "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter/devatlas/demo/*"
    ]
  }

  statement {
    sid       = "ListBackupBucket"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.backup.arn]
  }

  statement {
    sid       = "WriteBackups"
    actions   = ["s3:GetObject", "s3:PutObject"]
    resources = ["${aws_s3_bucket.backup.arn}/postgres/*"]
  }
}

resource "aws_iam_role_policy" "runtime" {
  name   = "${local.name}-runtime"
  role   = aws_iam_role.app.id
  policy = data.aws_iam_policy_document.runtime.json
}

resource "aws_iam_instance_profile" "app" {
  name = "${local.name}-instance-profile"
  role = aws_iam_role.app.name
}
